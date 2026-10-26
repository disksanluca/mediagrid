"""Approved storyboard -> immutable existing EDL v2 carried by a leased Job."""

from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException
from pydantic import Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..edl_v2 import EDLV2, TimelineItem, TimelineTrack, from_legacy, scene_projection
from ..ingestion import sha256_file
from ..models import (
    CreativeBriefRevision,
    CreativeDirectionSet,
    CreativeDNARevision,
    CreativeStoryboardRevision,
    Job,
)
from ..render_plan import probe_source, render_props
from ..scene_media import sound_asset
from ..services import record_event
from .contracts import StrictModel
from .hashing import content_sha256
from .service import latest, project_for, review_read, serialized

PRESET = "sports_cinematic_v1"
PHASES = ("impact", "reveal", "play", "resolve")
DURATIONS = (2000, 3000, 4000, 3000)


class MotionRequest(StrictModel):
    expected_storyboard_revision: int = Field(ge=1)
    expected_snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    soundtrack_asset_id: str = Field(min_length=1, max_length=36)
    quality: Literal["preview", "final"] = "preview"
    art_direction: Literal["original", "editorial", "broadcast", "broadcast_final"] = "original"
    diagnostics: bool = False
    sound_design_asset_id: str | None = Field(default=None, min_length=1, max_length=36)

    @model_validator(mode="after")
    def refinement_audio(self) -> "MotionRequest":
        if self.art_direction == "original" and self.sound_design_asset_id:
            raise ValueError("Original M3 uses its approved soundtrack")
        if self.art_direction != "original" and (
            not self.sound_design_asset_id or self.sound_design_asset_id == self.soundtrack_asset_id
        ):
            raise ValueError("Refinement requires a distinct, licensed sound-design asset")
        return self


def runtime_manifest() -> dict:
    root = (
        get_settings().mediagrid_renderer_root
        or Path(__file__).resolve().parents[3] / "apps" / "renderer"
    )
    files = sorted((root / "src").rglob("*.ts*"))
    if not files:
        raise HTTPException(409, "Renderer source is unavailable on this worker")
    return {
        "files": {
            str(path.relative_to(root)).replace("\\", "/"): sha256_file(path) for path in files
        },
        "package_sha256": sha256_file(root / "package.json"),
        "bridge_sha256": sha256_file(Path(__file__)),
    }


def derive_motion(db: Session, project_id: str, request: MotionRequest) -> dict:
    project = project_for(db, project_id)
    state = review_read(db, project)
    if (
        state["status"] != "APPROVED_STORYBOARD"
        or state["blockers"]
        or state["current_snapshot_sha256"] != request.expected_snapshot_sha256
    ):
        raise HTTPException(409, "A current approved storyboard and matching snapshot are required")
    board = latest(db, CreativeStoryboardRevision, project_id)
    if board.revision != request.expected_storyboard_revision:
        raise HTTPException(409, "Storyboard revision changed")
    brief = latest(db, CreativeBriefRevision, project_id)
    dna = latest(db, CreativeDNARevision, project.channel_id)
    directions = latest(db, CreativeDirectionSet, project_id)
    shots = board.payload["shots"]
    if (
        project.format != "vertical"
        or board.payload["fps"] != 30
        or board.payload["duration_ms"] != 12000
        or tuple(shot["duration_ms"] for shot in shots) != DURATIONS
        or brief.payload["factual_mode"] != "FICTIONAL"
    ):
        raise HTTPException(
            422, "M3 sports proof requires FICTIONAL, vertical, 30 fps, 2/3/4/3s shots"
        )
    if (
        dna.payload["font_display"] != "Barlow Condensed"
        or dna.payload["font_body"] != "Barlow Condensed"
        or len(dna.payload["palette"]) < 3
    ):
        raise HTTPException(
            422, "Sports preset requires Barlow Condensed and background/paper/accent"
        )
    ids = set(brief.payload["asset_ids"])
    if ids != {request.soundtrack_asset_id} or any(
        set(shot["asset_ids"]) != ids or shot["claim_ids"] for shot in shots
    ):
        raise HTTPException(
            422, "M3 uses original procedural visuals and one approved soundtrack per shot"
        )
    asset = sound_asset(db, request.soundtrack_asset_id)
    source = get_settings().mediagrid_data_dir / "assets" / asset.id
    if not asset.commercial_use or sha256_file(source) != asset.sha256:
        raise HTTPException(409, "Soundtrack rights or physical SHA-256 changed")
    try:
        duration = probe_source(source, "audio")
        if duration < 12 - 1 / 30:
            raise ValueError("Soundtrack is shorter than the approved storyboard")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    # Approved source remains untouched. The new mix belongs only to the derived
    # render plan; storyboard approval is not audiovisual approval of this mix.
    render_asset = asset
    if request.sound_design_asset_id:
        render_asset = sound_asset(db, request.sound_design_asset_id)
        path = get_settings().mediagrid_data_dir / "assets" / render_asset.id
        if not render_asset.commercial_use or sha256_file(path) != render_asset.sha256:
            raise HTTPException(409, "Sound design rights or physical SHA-256 changed")
        try:
            if abs(probe_source(path, "audio") - 12) > 1 / 30:
                raise ValueError("Sound design must match the 12-second storyboard")
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    legacy = {
        "version": 1,
        "format": "vertical",
        "tracks": {
            "video": [
                {
                    "scene_id": shot["id"],
                    "duration": shot["duration_ms"] / 1000,
                    "visual_type": "headline",
                    "transition": "cut",
                }
                for shot in shots
            ],
            "audio": [{"scene_id": shot["id"], "text": ""} for shot in shots],
            "captions": [{"scene_id": shot["id"], "text": ""} for shot in shots],
        },
    }
    edl = from_legacy(legacy, None, revision=board.revision)
    palette = dna.payload["palette"]
    overlays = []
    for shot, phase in zip(shots, PHASES, strict=True):
        duration_ms = shot["duration_ms"]
        overlays.append(
            TimelineItem(
                id=f"sports-{shot['id']}",
                start_ms=shot["start_ms"],
                duration_ms=duration_ms,
                z_index=10,
                preset=PRESET,
                params={
                    "text": shot["on_screen_text"],
                    "color": palette[2],
                    "background": palette[0],
                    "paper": palette[1],
                    "phase": phase,
                    "art_direction": request.art_direction,
                    "diagnostics": request.diagnostics,
                    "font_display": "Barlow Condensed",
                    "label": "ESTUDO ESPORTIVO / FICÇÃO",
                    "keyframes": [
                        {"at_ms": 0, "x": 0.5, "y": 0.5, "opacity": 0, "scale": 1.08},
                        {"at_ms": 400, "x": 0.5, "y": 0.5, "opacity": 1, "scale": 1},
                        {"at_ms": duration_ms - 300, "x": 0.5, "y": 0.5, "opacity": 1, "scale": 1},
                        {"at_ms": duration_ms, "x": 0.5, "y": 0.5, "opacity": 0.9, "scale": 1.03},
                    ],
                },
            )
        )
    edl.tracks.extend(
        [
            TimelineTrack(id="sports-design", kind="caption", items=overlays),
            TimelineTrack(
                id="score",
                kind="music",
                items=[
                    TimelineItem(
                        id="original-score",
                        start_ms=0,
                        duration_ms=12000,
                        source_asset_id=render_asset.id,
                        source_in_ms=0,
                        source_out_ms=12000,
                        preset="sound_v1",
                        params={"gain": 0.9, "fade_in_ms": 0, "fade_out_ms": 220, "loop": False},
                    )
                ],
            ),
        ]
    )
    try:
        edl = EDLV2.model_validate(edl.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    selected = next(
        item
        for item in directions.payload["directions"]
        if item["id"] == board.payload["direction_id"]
    )
    plan = {
        "schema_version": "creative_motion_v1",
        "project_id": project.id,
        "title": project.title,
        "approved_snapshot_sha256": state["current_snapshot_sha256"],
        "approval": state["review"],
        "storyboard": serialized(board),
        "brief": serialized(brief),
        "dna": serialized(dna),
        "direction": {
            "set_id": directions.id,
            "revision": directions.revision,
            "sha256": directions.sha256,
            "selected": selected,
        },
        "assets": [
            {
                "id": media.id,
                "sha256": media.sha256,
                "role": role,
                "rights_status": media.rights_status,
                "license_name": media.license_name,
                "creator": media.creator,
                "source_url": media.source_url,
                "commercial_use": media.commercial_use,
            }
            for media, role in (
                [(asset, "approved_soundtrack")]
                + ([(render_asset, "derived_sound_design")] if render_asset.id != asset.id else [])
            )
        ],
        "art_direction": request.art_direction,
        "diagnostics": request.diagnostics,
        "approval_scope": "STORYBOARD_INPUT_ONLY; DERIVED_AUDIOVISUAL_REVIEW_PENDING",
        "presets": [PRESET, "scene_v1", "scene_title_v1", "sound_v1"],
        "runtime": runtime_manifest(),
        "edl_v2": edl.model_dump(mode="json"),
        "render": {
            "composition": "MediaGridTimelineV2",
            "codec": "h264",
            "audio_codec": "aac",
            "fps": 30,
            "frames": 360,
            "width": 1080,
            "height": 1920,
            "scale": 0.5 if request.quality == "preview" else 1,
            "crf": 18,
            "audio_bitrate": "192k",
            "quality": request.quality,
        },
        "request": request.model_dump(mode="json"),
    }
    return {"plan": plan, "plan_sha256": content_sha256(plan)}


def verify_motion(db: Session, project_id: str, payload: dict) -> dict:
    if content_sha256(payload.get("plan")) != payload.get("plan_sha256"):
        raise ValueError("Derived motion payload hash mismatch")
    try:
        request = MotionRequest.model_validate(payload["plan"]["request"])
        fresh = derive_motion(db, project_id, request)
    except HTTPException as exc:
        raise ValueError(f"Creative motion blocked: {exc.detail}") from exc
    if fresh != payload:
        raise ValueError("Approved dependencies, runtime or derived plan changed after queueing")
    return payload["plan"]


def motion_props(plan: dict) -> dict:
    edl = EDLV2.model_validate(plan["edl_v2"])
    base, overlays, sounds, layers = scene_projection(edl, "vertical")
    # Transient projection only: never attach this object to a SQLAlchemy Session.
    projection = SimpleNamespace(title=plan["title"], format="vertical", plan=None, edl=base)
    return render_props(projection, None, base["tracks"]["video"], overlays, sounds, layers)


def queue_motion(db: Session, project_id: str, request: MotionRequest) -> Job:
    payload = derive_motion(db, project_id, request)
    identifier = str(uuid5(NAMESPACE_URL, "mediagrid:creative-motion:" + payload["plan_sha256"]))
    existing = db.get(Job, identifier)
    if existing:
        return existing
    job = Job(id=identifier, project_id=project_id, job_type="CREATIVE_MOTION", payload=payload)
    db.add(job)
    try:
        db.flush()
        record_event(
            db,
            "CREATIVE_MOTION_QUEUED",
            "job",
            job.id,
            after={"project_id": project_id, "plan_sha256": payload["plan_sha256"]},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(Job, identifier)
        if not existing:
            raise
        return existing
    return job


def motion_output(job_id: str) -> Path:
    return get_settings().mediagrid_data_dir / "creative-renders" / f"{job_id}.mp4"
