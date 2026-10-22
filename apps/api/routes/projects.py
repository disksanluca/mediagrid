import hashlib
import json
import os
import zipfile
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..edl_v2 import EDLV2, from_legacy, scene_projection
from ..engines import get_engine
from ..local_media import voice_matches
from ..models import Channel, Job, JobStatus, Project, ProjectRevision, ProjectStatus
from ..render_plan import fit_video_to_voice, probe_source, render_props
from ..scene_media import scene_asset, sound_asset, validate_scene_assets
from ..schemas import (
    ContentPlan,
    ProjectCreate,
    ProjectPlanUpdate,
    ProjectRead,
    ProjectReview,
    Scene,
)
from ..services import build_local_plan, create_plan, enqueue_job, record_event

router = APIRouter(prefix="/projects", tags=["projects"])


class RevisionWrite(BaseModel):
    expected_revision: int
    expected_legacy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    edl: EDLV2


def latest_revision(db: Session, project_id: str) -> ProjectRevision | None:
    return db.scalar(
        select(ProjectRevision)
        .where(ProjectRevision.project_id == project_id)
        .order_by(ProjectRevision.revision.desc())
        .limit(1)
    )


def append_revision(db: Session, project: Project, edl: EDLV2) -> ProjectRevision:
    encoded = json.dumps(
        edl.model_dump(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    revision = ProjectRevision(
        project_id=project.id,
        revision=edl.revision,
        edl=edl.model_dump(),
        sha256=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
    )
    db.add(revision)
    db.flush()
    return revision


def legacy_hash(edl: dict) -> str:
    encoded = json.dumps(edl, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def file_hash(path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def active_render_for(db: Session, project_id: str) -> Job | None:
    return db.scalar(select(Job).where(
        Job.project_id == project_id,
        Job.job_type == "RENDER",
        Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
    ))


@router.get("/{project_id}/edl-v2")
def read_edl_v2(project_id: str, response: Response, db: Session = Depends(get_db)) -> dict:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    if not project.edl:
        raise HTTPException(409, "Create a plan before opening the timeline")
    saved = latest_revision(db, project_id)
    current = saved.revision if saved else 0
    try:
        edl = from_legacy(project.edl, project.plan, revision=current + 1)
        if saved:
            stored = EDLV2.model_validate(saved.edl)
            projected, _, _, _ = scene_projection(stored, project.format)
            if projected == project.edl:
                edl = stored.model_copy(update={"revision": current + 1})
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    response.headers["ETag"] = f'"edl-{current}"'
    return {
        "revision": current,
        "legacy_sha256": legacy_hash(project.edl),
        "edl": edl.model_dump(),
        "renderer": "timeline-v2" if any(
            (track.kind in {"caption", "music", "sfx"}
             or track.kind == "video" and track.id != "picture") and track.items
            for track in edl.tracks
        ) else "scene-v1-compatible",
    }


@router.get("/{project_id}/preview")
def read_preview(project_id: str, db: Session = Depends(get_db)) -> dict:
    """Validated props for a browser preview of the saved visual composition."""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    if not project.edl or not project.plan or project.plan.get("origin") == "OUTLINE":
        raise HTTPException(409, "Complete and save the script before previewing")
    saved = latest_revision(db, project_id)
    overlays = []
    sounds = []
    video_layers = []
    using_saved = False
    if saved:
        try:
            canonical = EDLV2.model_validate(saved.edl)
            base, retained_overlays, retained_sounds, retained_videos = scene_projection(
                canonical, project.format
            )
            if base == project.edl:
                overlays, sounds, video_layers = (
                    retained_overlays, retained_sounds, retained_videos
                )
                using_saved = True
        except (ValueError, ValidationError) as exc:
            raise HTTPException(409, str(exc)) from exc
    scene_tracks = project.edl["tracks"]["video"]
    validate_scene_assets(db, scene_tracks)
    voice_path = get_settings().mediagrid_data_dir / "voice" / f"{project.id}.wav"
    valid_voice = voice_path if voice_matches(project.id, project.script) else None
    try:
        fitted, duration = fit_video_to_voice(
            scene_tracks, project.edl["tracks"]["audio"], valid_voice
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    props = render_props(
        project, db.get(Channel, project.channel_id),
        fitted, overlays, sounds, video_layers,
    )
    checked: set[str] = set()

    def check_hash(asset) -> None:
        if asset.id in checked:
            return
        path = get_settings().mediagrid_data_dir / "assets" / asset.id
        if file_hash(path) != asset.sha256:
            raise HTTPException(409, f"Source changed after import: {asset.name}")
        checked.add(asset.id)

    for scene in props["scenes"]:
        asset_id = scene.get("asset_id")
        if not asset_id:
            continue
        asset = scene_asset(db, asset_id)
        check_hash(asset)
        scene["media_kind"] = "video" if asset.media_type == "video/mp4" else "image"
        scene["media_file"] = asset.id
        if asset.media_type == "video/mp4":
            try:
                source_duration = probe_source(
                    get_settings().mediagrid_data_dir / "assets" / asset.id, "video"
                )
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            start = float(scene.get("clip_start_seconds") or 0)
            end = float(scene.get("clip_end_seconds") or source_duration)
            if start >= source_duration or end > source_duration + 0.05 or end <= start:
                raise HTTPException(422, "Scene clip exceeds its source MP4")
            scene["media_duration"] = source_duration
    for item in props.get("sounds", []):
        asset = sound_asset(db, item["source_asset_id"])
        check_hash(asset)
        item["media_file"] = asset.id
        try:
            source_duration = probe_source(
                get_settings().mediagrid_data_dir / "assets" / asset.id, "audio"
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        start = (item["source_in_ms"] or 0) / 1000
        end = (item["source_out_ms"] or source_duration * 1000) / 1000
        if start >= source_duration or end > source_duration + 0.05:
            raise HTTPException(422, "Sound source interval exceeds the audio file")
        if not item["loop"] and (end - start) * 1000 + 35 < item["duration_ms"]:
            raise HTTPException(422, "Sound item exceeds its audio source")
    for item in props.get("video_layers", []):
        asset = scene_asset(db, item["source_asset_id"])
        if asset.media_type != "video/mp4":
            raise HTTPException(422, "Video layer requires an MP4")
        check_hash(asset)
        item["media_file"] = asset.id
        try:
            source_duration = probe_source(
                get_settings().mediagrid_data_dir / "assets" / asset.id, "video"
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if item["source_out_ms"] / 1000 > source_duration + 0.05:
            raise HTTPException(422, "Video layer source interval exceeds its MP4")
    return {
        "revision": saved.revision if saved else 0,
        "revision_sha256": saved.sha256 if using_saved else legacy_hash(project.edl),
        "duration_seconds": duration,
        "voice_ready": valid_voice is not None,
        "props": props,
    }


@router.put("/{project_id}/edl-v2")
def write_edl_v2(project_id: str, payload: RevisionWrite, db: Session = Depends(get_db)) -> dict:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    current = latest_revision(db, project_id)
    current_number = current.revision if current else 0
    if (
        payload.expected_revision != current_number
        or payload.edl.revision != current_number + 1
        or not project.edl
        or payload.expected_legacy_sha256 != legacy_hash(project.edl)
    ):
        raise HTTPException(409, "Timeline changed; reload before saving")
    if active_render_for(db, project_id):
        raise HTTPException(409, "Wait for the current render before editing")
    try:
        legacy, _, sounds, video_layers = scene_projection(payload.edl, project.format)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    validate_scene_assets(db, legacy["tracks"]["video"])
    for item in sounds:
        sound_asset(db, item.source_asset_id)
    for item in video_layers:
        if scene_asset(db, item.source_asset_id).media_type != "video/mp4":
            raise HTTPException(422, "Video layers require an MP4 asset")
    if not project.plan:
        raise HTTPException(409, "Project plan is missing")
    previous_scenes = {scene["id"]: scene for scene in project.plan.get("scenes", [])}
    audio = {item["scene_id"]: item for item in legacy["tracks"]["audio"]}
    captions = {item["scene_id"]: item for item in legacy["tracks"]["captions"]}
    pictures = {
        item.params["scene_id"]: item
        for track in payload.edl.tracks if track.id == "picture" for item in track.items
    }
    scenes = []
    for item in legacy["tracks"]["video"]:
        scene_id = item["scene_id"]
        source = previous_scenes.get(scene_id, {})
        try:
            scene = Scene.model_validate({
                **source,
                "id": scene_id,
                "duration_seconds": item["duration"],
                "narration": audio[scene_id]["text"],
                "on_screen_text": captions[scene_id]["text"],
                "visual_type": item["visual_type"],
                "visual_query": pictures[scene_id].params.get(
                    "visual_query", source.get("visual_query", "")
                ),
                "transition": item["transition"],
                "asset_id": item["asset_id"],
                "clip_start_seconds": item["clip_start_seconds"],
                "clip_end_seconds": item["clip_end_seconds"],
            })
        except ValidationError as exc:
            raise HTTPException(422, exc.errors()) from exc
        scenes.append(scene)
    old_origin = project.plan.get("origin")
    unchanged = [scene.model_dump() for scene in scenes] == project.plan.get("scenes")
    still_outline = old_origin == "OUTLINE" and any(
        scene.narration.strip() == previous_scenes.get(scene.id, {}).get("narration", "").strip()
        for scene in scenes
    )
    plan = ContentPlan.model_validate({
        **project.plan,
        "scenes": [scene.model_dump() for scene in scenes],
        "origin": old_origin if unchanged else "OUTLINE" if still_outline else "MANUAL",
        "target_duration_seconds": round(payload.edl.duration_ms / 1000),
    })
    project.plan = {key: value for key, value in plan.model_dump().items() if key != "review"}
    channel = db.get(Channel, project.channel_id)
    if channel is None:
        raise HTTPException(404, "Channel not found")
    project.script = {
        "language": channel.language,
        "segments": [scene.narration for scene in scenes],
    }
    project.edl = legacy
    project.status = ProjectStatus.SCRIPTED.value
    try:
        saved = append_revision(db, project, payload.edl)
        record_event(db, "EDL_REVISION_SAVED", "project", project.id, after={
            "revision": saved.revision, "sha256": saved.sha256,
        })
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Timeline changed; reload before saving") from exc
    return {"revision": saved.revision, "sha256": saved.sha256, "project_id": project.id}


@router.get("", response_model=list[ProjectRead])
def list_projects(channel_id: str | None = None, db: Session = Depends(get_db)) -> list[Project]:
    statement = select(Project).order_by(Project.created_at.desc())
    if channel_id:
        statement = statement.where(Project.channel_id == channel_id)
    return list(db.scalars(statement))


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    if db.get(Channel, payload.channel_id) is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    project = Project(**payload.model_dump())
    db.add(project)
    db.flush()
    record_event(
        db, "PROJECT_CREATED", "project", project.id, after=payload.model_dump(mode="json")
    )
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db)) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/plan", response_model=ContentPlan)
def plan_project(project_id: str, db: Session = Depends(get_db)) -> ContentPlan:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if active_render_for(db, project_id):
        raise HTTPException(409, "Wait for the current render before editing")
    previous = latest_revision(db, project_id)
    plan = create_plan(db, project)
    channel = db.get(Channel, project.channel_id)
    try:
        if project.edl and project.format in {"vertical", "horizontal", "square"}:
            append_revision(db, project, from_legacy(
                project.edl, project.plan, revision=(previous.revision if previous else 0) + 1,
            ))
        if (
            channel
            and plan.origin != "OUTLINE"
            and (channel.editorial_profile or {}).get("auto_render") is True
        ):
            enqueue_job(db, project.id, "RENDER", {"edl": project.edl})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Timeline changed; reload before saving") from exc
    return plan


@router.put("/{project_id}/plan", response_model=ProjectRead)
def update_plan(
    project_id: str, payload: ProjectPlanUpdate, db: Session = Depends(get_db)
) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if active_render_for(db, project_id):
        raise HTTPException(409, "Wait for the current render before editing")
    current_revision = latest_revision(db, project_id)
    number = current_revision.revision if current_revision else 0
    if payload.expected_revision is not None and payload.expected_revision != number:
        raise HTTPException(409, "Timeline changed; reload before saving")
    if payload.expected_legacy_sha256 is not None and (
        not project.edl or payload.expected_legacy_sha256 != legacy_hash(project.edl)
    ):
        raise HTTPException(409, "Timeline changed; reload before saving")
    channel = db.get(Channel, project.channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    scene_ids = [scene.id for scene in payload.scenes]
    if len(scene_ids) != len(set(scene_ids)):
        raise HTTPException(422, "Scene IDs must be unique")
    validate_scene_assets(db, payload.scenes)
    original_narrations = {
        scene.id: scene.narration.strip()
        for scene in build_local_plan(project, channel).scenes
    }
    still_outline = (project.plan or {}).get("origin") == "OUTLINE" and any(
        scene.narration.strip() == original_narrations.get(scene.id)
        for scene in payload.scenes
    )
    plan = ContentPlan(
        project_id=project.id,
        engine=channel.default_engine,
        origin="OUTLINE" if still_outline else "MANUAL",
        hook=payload.hook,
        angle=payload.angle,
        target_duration_seconds=round(sum(scene.duration_seconds for scene in payload.scenes)),
        scenes=payload.scenes,
        requires_fact_review=True,
        review_checks=(project.plan or {}).get("review_checks")
        or list(get_engine(channel.default_engine).review_checks),
        source_refs=(project.plan or {}).get("source_refs", []),
    )
    project.plan = plan.model_dump()
    project.script = {"language": channel.language, "segments": [s.narration for s in plan.scenes]}
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
                    "asset_id": s.asset_id,
                    "clip_start_seconds": s.clip_start_seconds,
                    "clip_end_seconds": s.clip_end_seconds,
                }
                for s in plan.scenes
            ],
            "audio": [{"scene_id": s.id, "text": s.narration} for s in plan.scenes],
            "captions": [{"scene_id": s.id, "text": s.on_screen_text} for s in plan.scenes],
        },
    }
    project.status = ProjectStatus.SCRIPTED.value
    try:
        if project.format in {"vertical", "horizontal", "square"}:
            revised = from_legacy(
                project.edl, project.plan, revision=number + 1,
            )
            if current_revision:
                prior = EDLV2.model_validate(current_revision.edl)
                extra_tracks = [
                    track for track in prior.tracks
                    if track.kind in {"caption", "music", "sfx"}
                    or track.kind == "video" and track.id != "picture"
                ]
                if extra_tracks:
                    try:
                        revised = EDLV2.model_validate({
                            **revised.model_dump(),
                            "tracks": [
                                *[track.model_dump() for track in revised.tracks],
                                *[track.model_dump() for track in extra_tracks],
                            ],
                        })
                    except ValidationError as exc:
                        raise HTTPException(422, "Layer exceeds the revised timeline") from exc
            append_revision(db, project, revised)
        record_event(
            db, "SCRIPT_EDITED", "project", project.id,
            after={"scene_count": len(plan.scenes)},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Timeline changed; reload before saving") from exc
    db.refresh(project)
    return project


@router.post("/{project_id}/render", status_code=status.HTTP_202_ACCEPTED)
def queue_render(project_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.edl:
        raise HTTPException(status_code=409, detail="Create a validated plan before rendering")
    if (project.plan or {}).get("origin") == "OUTLINE":
        raise HTTPException(
            status_code=409,
            detail="O plano ainda é um esboço. Revise e salve a narração antes do render.",
        )
    if any(
        not str(scene.get("narration", "")).strip()
        for scene in (project.plan or {}).get("scenes", [])
    ):
        raise HTTPException(409, "Preencha a narração de todas as cenas antes do render.")
    validate_scene_assets(db, project.edl["tracks"]["video"])
    active = db.scalars(
        select(Job).where(
            Job.project_id == project_id,
            Job.job_type == "RENDER",
            Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
        )
    ).first()
    if active:
        raise HTTPException(status_code=409, detail="Render is already queued or running")
    active_voice = db.scalar(
        select(Job).where(
            Job.project_id == project_id,
            Job.job_type == "VOICE",
            Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
        )
    )
    if active_voice:
        raise HTTPException(409, "Aguarde a geração da nova voz antes de renderizar.")
    if project.status in {ProjectStatus.QC.value, ProjectStatus.APPROVED.value}:
        was_approved = project.status == ProjectStatus.APPROVED.value
        project.plan = {
            key: value for key, value in (project.plan or {}).items() if key != "review"
        }
        project.status = ProjectStatus.SCRIPTED.value
        record_event(
            db,
            "PROJECT_APPROVAL_REVOKED" if was_approved else "PROJECT_OUTPUT_INVALIDATED",
            "project",
            project.id,
        )
    payload = {"edl": project.edl}
    saved = latest_revision(db, project.id)
    if saved:
        try:
            canonical = EDLV2.model_validate(saved.edl)
            base, overlays, sounds, video_layers = scene_projection(canonical, project.format)
            if (overlays or sounds or video_layers) and base == project.edl:
                for item in sounds:
                    sound_asset(db, item.source_asset_id)
                for item in video_layers:
                    if scene_asset(db, item.source_asset_id).media_type != "video/mp4":
                        raise HTTPException(422, "Video layers require an MP4 asset")
                payload["edl_v2"] = saved.edl
        except ValueError as exc:
            raise HTTPException(409, f"Invalid timeline revision: {exc}") from exc
    job = enqueue_job(db, project.id, "RENDER", payload)
    db.commit()
    return {"job_id": job.id, "status": job.status}


@router.post("/{project_id}/voice", status_code=status.HTTP_202_ACCEPTED)
def queue_voice(project_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    if not project.script:
        raise HTTPException(409, "Create a plan before generating voice")
    if (project.plan or {}).get("origin") == "OUTLINE":
        raise HTTPException(409, "Revise e salve a narração antes de gerar a voz.")
    if any(
        not str(scene.get("narration", "")).strip()
        for scene in (project.plan or {}).get("scenes", [])
    ):
        raise HTTPException(409, "Preencha a narração de todas as cenas antes de gerar a voz.")
    active = db.scalar(
        select(Job).where(
            Job.project_id == project_id,
            Job.job_type == "VOICE",
            Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
        )
    )
    if active:
        raise HTTPException(409, "Voice is already queued")
    active_render = db.scalar(
        select(Job).where(
            Job.project_id == project_id,
            Job.job_type == "RENDER",
            Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
        )
    )
    if active_render:
        raise HTTPException(409, "Aguarde o render atual antes de gerar uma nova voz.")
    if project.status in {ProjectStatus.QC.value, ProjectStatus.APPROVED.value}:
        was_approved = project.status == ProjectStatus.APPROVED.value
        project.plan = {
            key: value for key, value in (project.plan or {}).items() if key != "review"
        }
        project.status = ProjectStatus.SCRIPTED.value
        record_event(
            db,
            "PROJECT_APPROVAL_REVOKED" if was_approved else "PROJECT_OUTPUT_INVALIDATED",
            "project",
            project.id,
        )
    job = enqueue_job(db, project.id, "VOICE")
    db.commit()
    return {"job_id": job.id, "status": job.status}


@router.get("/{project_id}/voice")
def download_voice(project_id: str, db: Session = Depends(get_db)) -> FileResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    output = get_settings().mediagrid_data_dir / "voice" / f"{project_id}.wav"
    if not voice_matches(project_id, project.script):
        raise HTTPException(404, "Voice is not available")
    return FileResponse(output, media_type="audio/wav", filename=f"mediagrid-{project_id}.wav")


@router.get("/{project_id}/output")
def download_output(project_id: str, db: Session = Depends(get_db)) -> FileResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status not in {ProjectStatus.QC.value, ProjectStatus.APPROVED.value}:
        raise HTTPException(status_code=404, detail="Render is not available")
    output = get_settings().mediagrid_data_dir / "renders" / f"{project_id}.mp4"
    if not output.is_file():
        raise HTTPException(status_code=404, detail="Render is not available")
    return FileResponse(output, media_type="video/mp4", filename=f"mediagrid-{project_id}.mp4")


@router.post("/{project_id}/review", response_model=ProjectRead)
def approve_project_review(
    project_id: str, payload: ProjectReview, db: Session = Depends(get_db)
) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    if project.status != ProjectStatus.QC.value:
        raise HTTPException(409, "A completed render is required before review")
    output = get_settings().mediagrid_data_dir / "renders" / f"{project_id}.mp4"
    if not output.is_file():
        raise HTTPException(409, "Rendered MP4 is missing")
    if not payload.facts_confirmed or not payload.rights_confirmed:
        raise HTTPException(409, "Confirm facts and media rights before approval")
    review = {
        "approved_at": datetime.now(UTC).isoformat(),
        "source_urls": [str(url) for url in payload.source_urls],
        "facts_confirmed": True,
        "rights_confirmed": True,
        "notes": payload.notes,
        "caption": payload.caption,
        "edl_sha256": legacy_hash(project.edl),
        "video_sha256": file_hash(output),
    }
    current = latest_revision(db, project_id)
    if current:
        review["revision"] = current.revision
        review["revision_sha256"] = current.sha256
    project.plan = {**(project.plan or {}), "review": review}
    project.status = ProjectStatus.APPROVED.value
    record_event(db, "PROJECT_APPROVED", "project", project.id, after=review)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}/export")
def export_reviewed_project(project_id: str, db: Session = Depends(get_db)) -> FileResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    review = (project.plan or {}).get("review")
    if project.status != ProjectStatus.APPROVED.value or not review:
        raise HTTPException(409, "Human review and approval are required")
    data_dir = get_settings().mediagrid_data_dir
    video = data_dir / "renders" / f"{project_id}.mp4"
    if not video.is_file():
        raise HTTPException(404, "Rendered MP4 is missing")
    if review.get("edl_sha256") != legacy_hash(project.edl) or (
        review.get("video_sha256") != file_hash(video)
    ):
        raise HTTPException(409, "Approved content changed; render and review again")
    current = latest_revision(db, project_id)
    if review.get("revision_sha256") and (
        not current or review["revision_sha256"] != current.sha256
    ):
        raise HTTPException(409, "Approved timeline changed; review again")
    exports = data_dir / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    target = exports / f"{project_id}.zip"
    temporary = exports / f".{project_id}.{uuid4().hex}.partial"
    manifest = {
        "format": "MediaGrid Manual Export",
        "project_id": project.id,
        "title": project.title,
        "channel_id": project.channel_id,
        "approved_review": review,
        "publication": "manual",
        "platform_status": "not_published",
    }
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.write(video, "video.mp4")
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            if review.get("caption"):
                archive.writestr("caption.txt", review["caption"])
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return FileResponse(
        target, media_type="application/zip", filename=f"mediagrid-{project_id}.zip"
    )
