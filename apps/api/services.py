import shutil
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .engines import get_engine
from .models import Channel, Event, Job, JobStatus, Project, ProjectStatus
from .schemas import ContentPlan, Scene


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
    scene_duration = duration / 5
    topic = project.topic.strip()
    scenes = [
        Scene(
            id="hook",
            duration_seconds=scene_duration,
            narration=f"Você precisa entender isto sobre {topic}.",
            visual_type="headline",
            visual_query=topic,
            on_screen_text=project.title,
            transition="impact",
        ),
        Scene(
            id="context",
            duration_seconds=scene_duration,
            narration=f"Primeiro, vamos colocar {topic} em contexto com informações verificáveis.",
            visual_type=engine.visual_types[1],
            visual_query=f"{topic} contexto",
            on_screen_text="O contexto",
            transition="slide",
        ),
        Scene(
            id="evidence",
            duration_seconds=scene_duration,
            narration="Os dados e as fontes do dossiê sustentam os pontos centrais desta história.",
            visual_type=engine.visual_types[2],
            visual_query=f"{topic} dados",
            on_screen_text="O que os dados mostram",
            transition="cut",
        ),
        Scene(
            id="meaning",
            duration_seconds=scene_duration,
            narration="O mais importante é o que isso muda para quem acompanha o assunto.",
            visual_type=engine.visual_types[3],
            visual_query=f"{topic} impacto",
            on_screen_text="Por que isso importa",
            transition="zoom",
        ),
        Scene(
            id="outro",
            duration_seconds=scene_duration,
            narration="Acompanhe o canal para mais conteúdo pesquisado e explicado com clareza.",
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
        angle=f"Explicar {topic} com clareza e contexto",
        target_duration_seconds=duration,
        scenes=scenes,
        requires_fact_review=engine.requires_fact_review,
    )


def create_plan(db: Session, project: Project) -> ContentPlan:
    channel = db.get(Channel, project.channel_id)
    if channel is None:
        raise ValueError("Project channel does not exist")
    before = {"status": project.status}
    project.status = ProjectStatus.SCRIPTING.value
    plan = build_local_plan(project, channel)
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
    record_event(db, f"{job_type}_QUEUED", "job", job.id, after={"project_id": project_id})
    return job


def claim_next_job(db: Session, job_type: str | None = None) -> Job | None:
    statement = select(Job).where(Job.status == JobStatus.QUEUED.value)
    if job_type:
        statement = statement.where(Job.job_type == job_type)
    statement = (
        statement.order_by(Job.priority.asc(), Job.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = db.scalar(statement)
    if job:
        job.status = JobStatus.RUNNING.value
        job.attempt += 1
        job.progress = 0.01
    return job


async def ollama_connected() -> bool:
    try:
        async with httpx.AsyncClient(timeout=0.5) as client:
            response = await client.get(f"{get_settings().ollama_base_url}/api/tags")
            return response.is_success
    except httpx.HTTPError:
        return False


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None
