import json
import logging
import shutil
from collections.abc import Sequence
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .config import get_settings
from .engines import get_engine
from .models import Channel, Event, Job, JobStatus, Project, ProjectStatus, now
from .schemas import ContentPlan, Scene

logger = logging.getLogger(__name__)
LOCAL_WORKER_ID = f"local-{uuid4().hex}"


def local_ollama_url() -> str | None:
    url = get_settings().ollama_base_url.rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return None
    return url


def enrich_plan_with_local_ai(plan: ContentPlan, topic: str) -> ContentPlan:
    base_url = local_ollama_url()
    if base_url is None:
        return plan
    prompt = (
        "Escreva narração em português brasileiro para um vídeo sobre: "
        + topic[:1000]
        + ". Responda somente JSON com a chave 'narrations' contendo exatamente "
        + str(len(plan.scenes))
        + " textos curtos, um por cena. Não invente fatos, números ou fontes. "
        + "Use linguagem clara e marque qualquer dado que precise de revisão."
    )
    try:
        with httpx.Client(timeout=httpx.Timeout(90, connect=0.5), trust_env=False) as client:
            tags = client.get(f"{base_url}/api/tags")
            tags.raise_for_status()
            available = {item.get("name") for item in tags.json().get("models", [])}
            model = get_settings().ollama_model
            if not any(name == model or (name or "").startswith(f"{model}:") for name in available):
                return plan
            response = client.post(
                f"{base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
            )
            response.raise_for_status()
            narrations = json.loads(response.json()["response"])["narrations"]
            if not isinstance(narrations, list) or len(narrations) != len(plan.scenes):
                return plan
            if not all(
                isinstance(value, str) and 10 <= len(value.strip()) <= 600 for value in narrations
            ):
                return plan
            scenes = [
                scene.model_copy(update={"narration": text.strip()})
                for scene, text in zip(plan.scenes, narrations, strict=True)
            ]
            return plan.model_copy(
                update={"hook": scenes[0].narration, "scenes": scenes, "origin": "LOCAL_AI"}
            )
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        logger.info("Local Ollama unavailable; using built-in plan: %s", exc)
        return plan


def record_event(
    db: Session,
    event_type: str,
    entity_type: str,
    entity_id: str,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    db.add(
        Event(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
        )
    )


def build_local_plan(project: Project, channel: Channel) -> ContentPlan:
    engine = get_engine(channel.default_engine)
    is_vertical = project.format == "vertical"
    duration = 45 if is_vertical else 180
    brief_lines = [line.strip().lstrip("-• ").strip() for line in project.topic.splitlines()]
    brief_lines = [line for line in brief_lines if line]
    if 3 <= len(brief_lines) <= 5 and all(20 <= len(line) <= 300 for line in brief_lines):
        transitions = ("impact", "slide", "cut", "zoom", "fade")
        scenes = [
            Scene(
                id=f"brief-{index + 1}",
                duration_seconds=max(5, min(60, round(len(line.split()) / 2.2 + 2))),
                narration=line,
                visual_type=engine.visual_types[index % len(engine.visual_types)],
                visual_query=project.title,
                on_screen_text=line[:77] + ("…" if len(line) > 77 else ""),
                transition=transitions[index],
            )
            for index, line in enumerate(brief_lines)
        ]
        return ContentPlan(
            project_id=project.id,
            engine=engine.id,
            origin="BRIEF_BASED",
            hook=scenes[0].narration,
            angle=(
                "Roteiro baseado no briefing fornecido; "
                "confirme fatos e direitos antes de publicar."
            ),
            target_duration_seconds=round(sum(scene.duration_seconds for scene in scenes)),
            scenes=scenes,
            requires_fact_review=True,
            review_checks=list(engine.review_checks),
        )
    scene_duration = duration / 5
    topic = project.topic.strip()
    scenes = [
        Scene(
            id="hook",
            duration_seconds=scene_duration,
            narration=f"Apresente a pergunta principal sobre {topic}.",
            visual_type="headline",
            visual_query=topic,
            on_screen_text=project.title,
            transition="impact",
        ),
        Scene(
            id="context",
            duration_seconds=scene_duration,
            narration=f"{engine.scene_guidance[0]} Tema: {topic}.",
            visual_type=engine.visual_types[1],
            visual_query=f"{topic} contexto",
            on_screen_text="O contexto",
            transition="slide",
        ),
        Scene(
            id="evidence",
            duration_seconds=scene_duration,
            narration=engine.scene_guidance[1],
            visual_type=engine.visual_types[2],
            visual_query=f"{topic} dados",
            on_screen_text="O que os dados mostram",
            transition="cut",
        ),
        Scene(
            id="meaning",
            duration_seconds=scene_duration,
            narration=engine.scene_guidance[2],
            visual_type=engine.visual_types[3],
            visual_query=f"{topic} impacto",
            on_screen_text="Por que isso importa",
            transition="zoom",
        ),
        Scene(
            id="outro",
            duration_seconds=scene_duration,
            narration="Encerre com uma conclusão revisada e um convite para acompanhar o canal.",
            visual_type="outro",
            visual_query="brand outro",
            on_screen_text="Continue acompanhando",
            transition="fade",
        ),
    ]
    return ContentPlan(
        project_id=project.id,
        engine=engine.id,
        hook=scenes[0].narration,
        angle=f"Explicar {topic} com tom {engine.default_tone}",
        target_duration_seconds=duration,
        scenes=scenes,
        requires_fact_review=engine.requires_fact_review,
        review_checks=list(engine.review_checks),
    )


def create_plan(db: Session, project: Project) -> ContentPlan:
    channel = db.get(Channel, project.channel_id)
    if channel is None:
        raise ValueError("Project channel does not exist")
    before = {"status": project.status}
    project.status = ProjectStatus.SCRIPTING.value
    plan = build_local_plan(project, channel)
    if plan.origin == "OUTLINE":
        plan = enrich_plan_with_local_ai(plan, project.topic)
    project.plan = plan.model_dump()
    project.script = {
        "language": channel.language,
        "segments": [scene.narration for scene in plan.scenes],
    }
    project.edl = {
        "version": 1,
        "format": project.format,
        "tracks": {
            "video": [
                {
                    "scene_id": s.id,
                    "duration": s.duration_seconds,
                    "visual_type": s.visual_type,
                    "transition": s.transition,
                }
                for s in plan.scenes
            ],
            "audio": [{"scene_id": s.id, "text": s.narration} for s in plan.scenes],
            "captions": [{"scene_id": s.id, "text": s.on_screen_text} for s in plan.scenes],
        },
    }
    project.status = ProjectStatus.SCRIPTED.value
    record_event(
        db,
        "SCRIPT_GENERATED",
        "project",
        project.id,
        before=before,
        after={"status": project.status},
    )
    return plan


def enqueue_job(
    db: Session, project_id: str, job_type: str, payload: dict[str, Any] | None = None
) -> Job:
    job = Job(project_id=project_id, job_type=job_type, payload=payload or {})
    db.add(job)
    db.flush()
    record_event(db, f"{job_type}_{job.status}", "job", job.id,
                 after={"project_id": project_id})
    return job


def claim_next_job(db: Session, job_type: str | Sequence[str] | None = None,
                   *, worker_id: str = LOCAL_WORKER_ID) -> Job | None:
    statement = select(Job).where(Job.status == JobStatus.QUEUED.value)
    if isinstance(job_type, str):
        statement = statement.where(Job.job_type == job_type)
    elif job_type:
        statement = statement.where(Job.job_type.in_(job_type))
    statement = (
        statement.order_by(Job.priority.asc(), Job.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = db.scalar(statement)
    if job:
        claimed_at = now()
        token = f"{worker_id}:{uuid4().hex}"
        with db.no_autoflush:
            result = db.execute(update(Job).where(
                Job.id == job.id, Job.status == JobStatus.QUEUED.value,
            ).values(status=JobStatus.RUNNING.value, attempt=Job.attempt + 1,
                     progress=0.01, started_at=claimed_at, heartbeat_at=claimed_at,
                     lease_owner=token,
                     lease_expires_at=claimed_at + timedelta(minutes=5)),
                execution_options={"synchronize_session": False})
        if result.rowcount != 1:
            db.expire(job)
            return None
        db.refresh(job)
    return job


def renew_job_lease(db: Session, job_id: str, worker_id: str,
                    *, ttl_seconds: int = 300) -> bool:
    if not worker_id or ttl_seconds <= 0:
        raise ValueError("A worker identity and positive lease duration are required")
    heartbeat = now()
    result = db.execute(update(Job).where(
        Job.id == job_id,
        Job.status == JobStatus.RUNNING.value,
        Job.lease_owner == worker_id,
        Job.lease_expires_at > heartbeat,
    ).values(heartbeat_at=heartbeat,
             lease_expires_at=heartbeat + timedelta(seconds=ttl_seconds)),
        execution_options={"synchronize_session": False})
    return result.rowcount == 1


def fence_job_completion(db: Session, job_id: str, lease_owner: str) -> bool:
    """Lock the active claim before committing a terminal state and its side effects."""
    if not lease_owner:
        return False
    with db.no_autoflush:
        result = db.execute(update(Job).where(
            Job.id == job_id,
            Job.status == JobStatus.RUNNING.value,
            Job.lease_owner == lease_owner,
            Job.lease_expires_at > now(),
        ).values(lease_owner=None, lease_expires_at=None),
            execution_options={"synchronize_session": False})
    return result.rowcount == 1


async def ollama_connected() -> bool:
    base_url = local_ollama_url()
    if base_url is None:
        return False
    try:
        async with httpx.AsyncClient(timeout=0.5, trust_env=False) as client:
            response = await client.get(f"{base_url}/api/tags")
            return response.is_success
    except httpx.HTTPError:
        return False


def ffmpeg_available() -> bool:
    configured = get_settings().mediagrid_ffmpeg_path
    return configured.is_file() if configured else shutil.which("ffmpeg") is not None
