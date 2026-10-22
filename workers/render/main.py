import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import time
import wave
from contextlib import closing
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from apps.api.config import get_settings
from apps.api.database import SessionLocal
from apps.api.local_media import narration_text, synthesize_voice, transcribe_media, voice_matches
from apps.api.models import Asset, Channel, Job, JobStatus, Project, ProjectStatus, now
from apps.api.scene_media import stage_scene_assets
from apps.api.services import claim_next_job, record_event

logger = logging.getLogger(__name__)


def source_label(plan: dict | None) -> str | None:
    for source in (plan or {}).get("source_refs", []):
        if not isinstance(source, dict):
            continue
        url = source.get("api_url")
        if isinstance(url, str) and urlparse(url).hostname == "dadosabertos.camara.leg.br":
            return "Fonte: Câmara dos Deputados"
        if isinstance(url, str) and urlparse(url).hostname == "servicodados.ibge.gov.br":
            return "Fonte: IBGE"
    return None


def fit_video_to_voice(
    video: list[dict], audio: list[dict], voice: Path | None
) -> tuple[list[dict], float]:
    """Keep every narration audible when local TTS runs longer than estimates."""
    tracks = [item.copy() for item in video]
    planned = sum(float(item["duration"]) for item in tracks)
    if voice is None:
        return tracks, planned
    try:
        with wave.open(str(voice), "rb") as wav:
            voice_seconds = wav.getnframes() / wav.getframerate()
    except (OSError, wave.Error, ZeroDivisionError) as exc:
        raise ValueError("Generated voice is not a readable WAV") from exc
    required = voice_seconds + 1.0
    if required > planned:
        weights = [
            max(1, len(str(item.get("text", "")).split())) for item in audio
        ]
        if len(weights) != len(tracks):
            raise ValueError("Voice and video scene counts do not match")
        total_weight = sum(weights)
        for item, weight in zip(tracks, weights, strict=True):
            item["duration"] = (
                float(item["duration"]) + (required - planned) * weight / total_weight
            )
    return tracks, sum(float(item["duration"]) for item in tracks)


def validate_video(path: Path) -> dict[str, object]:
    ffprobe = get_settings().mediagrid_ffprobe_path or "ffprobe"
    result = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    metadata = json.loads(result.stdout)
    duration = float(metadata.get("format", {}).get("duration", 0))
    video = next(
        (stream for stream in metadata.get("streams", []) if stream.get("codec_type") == "video"),
        None,
    )
    if duration <= 0 or not video or not video.get("width") or not video.get("height"):
        raise ValueError("Rendered MP4 has no valid video stream")
    return {"duration_seconds": duration, "width": video["width"], "height": video["height"]}


def recover_interrupted_jobs() -> None:
    with SessionLocal() as db:
        jobs = db.scalars(
            select(Job).where(
                Job.job_type.in_(["RENDER", "VOICE", "TRANSCRIBE"]),
                Job.status == JobStatus.RUNNING.value,
            )
        ).all()
        for job in jobs:
            project = db.get(Project, job.project_id) if job.project_id else None
            if job.attempt < job.max_attempts:
                job.status = JobStatus.QUEUED.value
                job.progress = 0
                if project:
                    project.status = ProjectStatus.SCRIPTED.value
            else:
                job.status = JobStatus.FAILED.value
                job.error = "Local job was interrupted and reached the retry limit"
                job.finished_at = now()
                if project and job.job_type == "RENDER":
                    project.status = ProjectStatus.FAILED.value
                    project.error = job.error
        db.commit()


def render_one() -> bool:
    settings = get_settings()
    with SessionLocal() as db:
        job = claim_next_job(db, "RENDER")
        if job is None:
            return False
        db.commit()
        if not job.project_id:
            job.status = JobStatus.FAILED.value
            job.error = "Render worker received an incompatible job"
            db.commit()
            return True
        project = db.get(Project, job.project_id)
        if project is None or not project.edl:
            job.status = JobStatus.FAILED.value
            job.error = "Project or EDL not found"
            db.commit()
            return True
        queued_edl = (job.payload or {}).get("edl")
        if queued_edl is not None and queued_edl != project.edl:
            job.status = JobStatus.FAILED.value
            job.error = "Project timeline changed after this render was queued"
            job.finished_at = now()
            record_event(db, "RENDER_STALE", "project", project.id, after={
                "job_id": job.id, "error": job.error,
            })
            db.commit()
            return True
        rendered_edl = queued_edl if queued_edl is not None else project.edl
        edl_sha256 = hashlib.sha256(json.dumps(
            rendered_edl, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()

        temp_dir = settings.mediagrid_data_dir / "temp"
        output_dir = settings.mediagrid_data_dir / "renders"
        temp_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        props_path = (temp_dir / f"{job.id}.json").resolve()
        public_dir = (temp_dir / f"{job.id}-media").resolve()
        output_path = (output_dir / f"{project.id}.mp4").resolve()
        channel = db.get(Channel, project.channel_id)
        configured_accent = (channel.brand_profile or {}).get("accent") if channel else None
        accent = (
            configured_accent
            if isinstance(configured_accent, str)
            and re.fullmatch(r"#[0-9a-fA-F]{6}", configured_accent)
            else "#c5ccd6"
        )
        captions = {item["scene_id"]: item["text"] for item in project.edl["tracks"]["captions"]}
        voice = settings.mediagrid_data_dir / "voice" / f"{project.id}.wav"
        valid_voice = voice if voice_matches(project.id, project.script) else None
        try:
            video_tracks, render_duration = fit_video_to_voice(
                project.edl["tracks"]["video"], project.edl["tracks"]["audio"], valid_voice
            )
        except ValueError as exc:
            job.status = JobStatus.FAILED.value
            job.error = str(exc)
            project.status = ProjectStatus.FAILED.value
            db.commit()
            return True
        props = {
            "title": project.title,
            "format": project.format,
            "accent": accent,
            "source_label": source_label(project.plan),
            "scenes": [
                dict(item, on_screen_text=captions.get(item["scene_id"]))
                for item in video_tracks
            ],
        }
        project.status = ProjectStatus.RENDERING.value
        db.commit()
        try:
            staged = stage_scene_assets(db, video_tracks, public_dir)
            for media in staged.values():
                if media["media_kind"] == "video":
                    info = validate_video(public_dir / media["media_file"])
                    media["media_duration"] = info["duration_seconds"]
            for scene in props["scenes"]:
                scene.update(staged.get(scene.get("asset_id"), {}))
                if scene.get("media_kind") == "video":
                    start = float(scene.get("clip_start_seconds") or 0)
                    duration = float(scene["media_duration"])
                    end = float(scene.get("clip_end_seconds") or duration)
                    if start >= duration or end > duration + 0.05 or end <= start:
                        raise ValueError(
                            "Trecho do clipe fora da duração do MP4. Ajuste início e fim no Editor."
                        )
            props_path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
            renderer_root = (
                settings.mediagrid_renderer_root.resolve()
                if settings.mediagrid_renderer_root
                else None
            )
            node = settings.mediagrid_node_path
            if renderer_root and node:
                cli = renderer_root / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
                if not cli.is_file():
                    # npm workspaces hoist the CLI to the repository root in development.
                    cli = (
                        renderer_root.parents[1]
                        / "node_modules"
                        / "@remotion"
                        / "cli"
                        / "remotion-cli.js"
                    )
                if not cli.is_file():
                    raise ValueError("Remotion CLI not found in renderer runtime or workspace")
                command = [
                    str(node),
                    str(cli),
                    "render",
                    str(renderer_root / "src" / "index.ts"),
                    "MediaGridVideo",
                    str(output_path),
                    "--props",
                    str(props_path),
                ]
                browser = (
                    str(settings.mediagrid_browser_path)
                    if settings.mediagrid_browser_path
                    else next(
                        (
                            str(path)
                            for path in (renderer_root / "node_modules" / ".remotion").rglob(
                                "chrome-headless-shell.exe"
                            )
                        ),
                        None,
                    )
                )
            else:
                command = [
                    "npm",
                    "run",
                    "render",
                    "--workspace",
                    "@mediagrid/renderer",
                    "--",
                    str(output_path),
                    "--props",
                    str(props_path),
                ]
                browser = shutil.which("chromium") or shutil.which("google-chrome")
            if browser:
                command.append(f"--browser-executable={browser}")
            command.append(f"--public-dir={public_dir}")
            subprocess.run(command, check=True, cwd=renderer_root if renderer_root else None)
            if valid_voice is not None:
                voiced = temp_dir / f"{job.id}-voiced.mp4"
                ffmpeg = settings.mediagrid_ffmpeg_path or "ffmpeg"
                subprocess.run(
                    [
                        str(ffmpeg),
                        "-y",
                        "-i",
                        str(output_path),
                        "-i",
                        str(voice),
                        "-map",
                        "0:v:0",
                        "-map",
                        "1:a:0",
                        "-c:v",
                        "copy",
                        "-c:a",
                        "aac",
                        "-af",
                        "apad",
                        "-t",
                        str(render_duration),
                        str(voiced),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                voiced.replace(output_path)
            video_info = validate_video(output_path)
            job.status = JobStatus.SUCCEEDED.value
            job.progress = 1
            digest = hashlib.sha256()
            with output_path.open("rb") as rendered:
                for chunk in iter(lambda: rendered.read(1024 * 1024), b""):
                    digest.update(chunk)
            job.result = {
                "output": str(output_path), "sha256": digest.hexdigest(),
                "edl_sha256": edl_sha256, **video_info,
            }
            job.finished_at = now()
            project.status = ProjectStatus.QC.value
            record_event(db, "RENDER_FINISHED", "project", project.id, after=job.result)
        except (
            subprocess.CalledProcessError,
            ValueError,
            OSError,
            json.JSONDecodeError,
            HTTPException,
        ) as exc:
            job.status = JobStatus.FAILED.value
            detail = exc.detail if isinstance(exc, HTTPException) else exc
            job.error = f"Render validation failed: {detail}"
            job.finished_at = now()
            project.status = ProjectStatus.FAILED.value
            project.error = job.error
            record_event(db, "RENDER_FAILED", "project", project.id, after={"error": job.error})
        finally:
            props_path.unlink(missing_ok=True)
            if public_dir.parent == temp_dir.resolve() and public_dir.name == f"{job.id}-media":
                shutil.rmtree(public_dir, ignore_errors=True)
            db.commit()
        return True


def media_one() -> bool:
    settings = get_settings()
    with SessionLocal() as db:
        job = db.scalar(
            select(Job)
            .where(
                Job.status == JobStatus.QUEUED.value,
                Job.job_type.in_(["VOICE", "TRANSCRIBE"]),
            )
            .order_by(Job.priority, Job.created_at)
            .limit(1)
        )
        if job is None:
            return False
        job.status = JobStatus.RUNNING.value
        job.attempt += 1
        job.started_at = now()
        db.commit()
        try:
            if job.job_type == "VOICE":
                project = db.get(Project, job.project_id) if job.project_id else None
                if project is None or not project.script:
                    raise ValueError("Project or script not found")
                output = settings.mediagrid_data_dir / "voice" / f"{project.id}.wav"
                text = narration_text(project.script)
                synthesize_voice(text, output)
                output.with_suffix(".sha256").write_text(
                    hashlib.sha256(text.encode("utf-8")).hexdigest()
                )
            else:
                asset_id = job.payload.get("asset_id")
                asset = db.get(Asset, asset_id) if asset_id else None
                if asset is None:
                    raise ValueError("Asset not found")
                source = settings.mediagrid_data_dir / "assets" / asset.id
                if not source.is_file():
                    raise ValueError("Asset file not found")
                output = settings.mediagrid_data_dir / "transcripts" / f"{asset.id}.txt"
                transcribe_media(source, output)
            job.status = JobStatus.SUCCEEDED.value
            job.progress = 1
            job.result = {"output": str(output)}
            record_event(db, f"{job.job_type}_FINISHED", "job", job.id, after=job.result)
        except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
            job.status = JobStatus.FAILED.value
            job.error = str(exc)
            record_event(db, f"{job.job_type}_FAILED", "job", job.id, after={"error": job.error})
        job.finished_at = now()
        db.commit()
        return True


def backup_local_database() -> None:
    settings = get_settings()
    if not settings.database_url.startswith("sqlite:///"):
        return
    database = Path(settings.database_url.removeprefix("sqlite:///"))
    if not database.is_file():
        return
    from datetime import date

    folder = settings.mediagrid_data_dir / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"mediagrid-{date.today().isoformat()}.db"
    if target.is_file():
        return
    # Separate workers may start together. A shared .tmp path can lock and kill
    # the worker before it has a chance to process queued renders.
    temporary = folder / f".{target.stem}.{uuid4().hex}.tmp"
    try:
        with (
            closing(sqlite3.connect(database)) as source,
            closing(sqlite3.connect(temporary)) as destination,
        ):
            source.backup(destination)
        if not target.is_file():
            os.replace(temporary, target)
    except OSError:
        logger.exception("Daily database backup failed; the worker will retry later")
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not remove temporary backup %s", temporary, exc_info=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="MediaGrid local worker")
    parser.add_argument("--once", action="store_true", help="Process at most one queued job")
    args = parser.parse_args(argv)
    recover_interrupted_jobs()
    backup_local_database()
    if args.once:
        if not media_one():
            render_one()
        return
    while True:
        backup_local_database()
        if not media_one() and not render_one():
            time.sleep(2)


if __name__ == "__main__":
    main()
