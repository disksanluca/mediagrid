"""Creative proof jobs use the existing Remotion composition, mixer and queue."""

import json
import shutil
import subprocess
from pathlib import Path
from time import perf_counter

from fastapi import HTTPException
from sqlalchemy.orm import Session

from apps.api.config import get_settings
from apps.api.creative.motion import motion_output, motion_props, verify_motion
from apps.api.ingestion import sha256_file
from apps.api.models import Job
from apps.api.scene_media import stage_scene_assets, stage_sound_assets
from workers.render.remotion_runtime import render_remotion


def validate_motion_video(output: Path, plan: dict) -> dict:
    settings = get_settings()
    probe = subprocess.run(
        [
            str(settings.mediagrid_ffprobe_path or "ffprobe"),
            "-v",
            "error",
            "-count_frames",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    metadata = json.loads(probe.stdout)
    video = next((s for s in metadata["streams"] if s["codec_type"] == "video"), {})
    audio = next((s for s in metadata["streams"] if s["codec_type"] == "audio"), {})
    config = plan["render"]
    expected = (round(config["width"] * config["scale"]), round(config["height"] * config["scale"]))
    duration = config.get("duration_ms", 12000) / 1000
    audio_required = config.get("audio_required", True)
    if (
        video.get("codec_name") != "h264"
        or (audio_required and audio.get("codec_name") != "aac")
        or video.get("r_frame_rate") != "30/1"
        or video.get("avg_frame_rate") != "30/1"
        or int(video.get("nb_read_frames", 0)) != config.get("frames", 360)
        or (video.get("width"), video.get("height")) != expected
        or abs(float(video.get("duration", 0)) - duration) > 1 / 30
        or (audio_required and abs(float(audio.get("duration", 0)) - duration) > 0.06)
        or abs(float(metadata["format"]["duration"]) - duration) > 0.06
    ):
        raise ValueError(
            "MP4 does not meet the plan H.264/AAC, frame, duration or canvas requirements"
        )
    decode = subprocess.run(
        [
            str(settings.mediagrid_ffmpeg_path or "ffmpeg"),
            "-v",
            "error",
            "-i",
            str(output),
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    if decode.returncode or decode.stderr.strip():
        raise ValueError(f"MP4 decode failed: {decode.stderr[-500:]}")
    return metadata


def render_creative_motion(db: Session, job: Job, attempt_id: str, output: Path) -> dict:
    started = perf_counter()
    payload = job.payload
    plan = verify_motion(db, job.project_id, payload)
    temp = get_settings().mediagrid_data_dir / "temp"
    public = (temp / f"{attempt_id}-creative-media").resolve()
    props_file = (temp / f"{attempt_id}-creative.json").resolve()
    try:
        props = motion_props(plan)
        sounds = stage_sound_assets(db, {
            a["id"] for a in plan["assets"] if a.get("metadata", {}).get("kind", "audio") == "audio"
        }, public)
        visuals = stage_scene_assets(db, [
            {"asset_id": a["id"]} for a in plan["assets"]
            if a.get("metadata", {}).get("kind") in {"image", "video"}
        ], public)
        for item in props["sounds"]:
            item["media_file"] = sounds[item["source_asset_id"]]
        for item in props.get("overlays", []):
            if item["preset"] == "motion_scene_v1":
                item["motion"]["media_files"] = {
                    slot: (sounds[asset_id] if asset_id in sounds
                           else visuals[asset_id]["media_file"])
                    for slot, asset_id in item["motion"]["assets"].items()
                }
        props_file.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
        # Fresh database reads plus physical hashes immediately before invoking Remotion.
        db.expire_all()
        verify_motion(db, job.project_id, payload)
        render_remotion(
            props_file,
            public,
            output.resolve(),
            timeline=True,
            scale=plan["render"]["scale"],
            explicit_codecs=True,
        )
        probe = validate_motion_video(output, plan)
        db.expire_all()
        verify_motion(db, job.project_id, payload)
        target = motion_output(job.id)
        target.parent.mkdir(parents=True, exist_ok=True)
        return {
            "output": str(target),
            "sha256": sha256_file(output),
            "plan_sha256": payload["plan_sha256"],
            "approved_snapshot_sha256": plan["approved_snapshot_sha256"],
            "storyboard_sha256": plan["storyboard"]["sha256"],
            "ffprobe": probe,
            "render_seconds": round(perf_counter() - started, 3),
            "art_direction": plan.get("art_direction", "original"),
            "diagnostics": plan.get("diagnostics", False),
            "artistic_review": "AWAITING_HUMAN_REVIEW",
            "engine_schema": plan["schema_version"],
            "recipe": plan.get("request", {}).get("recipe"),
            "composition_sha256": plan.get("composition_sha256"),
            "dependencies_sha256": plan.get("dependencies_sha256"),
        }
    except HTTPException as exc:
        raise ValueError(str(exc.detail)) from exc
    finally:
        props_file.unlink(missing_ok=True)
        if public.parent == temp.resolve() and public.name == f"{attempt_id}-creative-media":
            shutil.rmtree(public, ignore_errors=True)
