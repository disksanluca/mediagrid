import argparse
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import time
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import or_, select

from apps.api.asr_words import transcribe_words
from apps.api.captions import group_words, probe_media, validate_timing
from apps.api.config import get_settings
from apps.api.database import SessionLocal
from apps.api.edl_v2 import EDLV2, scene_projection
from apps.api.ingestion import sha256_file
from apps.api.local_media import narration_text, synthesize_voice, transcribe_media, voice_matches
from apps.api.models import (
    Asset,
    Channel,
    ClipCandidate,
    FootballSequence,
    Job,
    JobStatus,
    Narrative3D,
    Project,
    ProjectRevision,
    ProjectStatus,
    Transcript,
    now,
)
from apps.api.render_plan import fit_video_to_voice, render_props
from apps.api.render_plan import source_label as source_label
from apps.api.scene_media import stage_scene_assets, stage_sound_assets
from apps.api.services import claim_next_job, fence_job_completion, record_event
from apps.api.transcripts import replace_words
from workers.render.artifacts import finish_media_render_attempt, finish_render_attempt
from workers.render.caption_video import burn_captions, caption_output
from workers.render.clips import analyze_asset, clip_output, render_selected_clip
from workers.render.football import football_output, render_football
from workers.render.lease import start_lease_heartbeat
from workers.render.narrative_3d import (
    blender_script,
    narrative_output,
    render_narrative,
    story_sha256,
)
from workers.render.proxy import build_proxy

logger = logging.getLogger(__name__)


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


def audio_duration(path: Path) -> float:
    ffprobe = get_settings().mediagrid_ffprobe_path or "ffprobe"
    result = subprocess.run(
        [str(ffprobe), "-v", "error", "-show_entries", "format=duration:stream=codec_type",
         "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    metadata = json.loads(result.stdout)
    duration = float(metadata.get("format", {}).get("duration", 0))
    if duration <= 0 or not any(
        stream.get("codec_type") == "audio" for stream in metadata.get("streams", [])
    ):
        raise ValueError("Sound asset has no valid audio stream")
    return duration


def recover_interrupted_jobs() -> None:
    with SessionLocal() as db:
        jobs = db.scalars(
            select(Job).where(
                Job.job_type.in_([
                    "RENDER", "VOICE", "TRANSCRIBE", "PROXY", "ASR_WORDS", "CAPTION_RENDER",
                    "CLIP_ANALYSIS", "CLIP_RENDER", "FOOTBALL_RENDER",
                    "NARRATIVE_3D_RENDER",
                ]),
                Job.status == JobStatus.RUNNING.value,
                or_(Job.lease_expires_at.is_(None), Job.lease_expires_at <= now()),
            )
        ).all()
        for job in jobs:
            project = db.get(Project, job.project_id) if job.project_id else None
            job.lease_owner = None
            job.lease_expires_at = None
            job.heartbeat_at = None
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
        lease_owner = job.lease_owner
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
        queued_v2 = (job.payload or {}).get("edl_v2")
        overlays = []
        sounds = []
        video_layers = []
        revision_sha256 = None
        if queued_v2 is not None:
            current = db.scalar(
                select(ProjectRevision)
                .where(ProjectRevision.project_id == project.id)
                .order_by(ProjectRevision.revision.desc())
                .limit(1)
            )
            try:
                canonical = EDLV2.model_validate(queued_v2)
                base, overlays, sounds, video_layers = scene_projection(
                    canonical, project.format
                )
                if not current or current.edl != queued_v2 or base != project.edl:
                    raise ValueError("Timeline revision changed after this render was queued")
                revision_sha256 = current.sha256
            except ValueError as exc:
                job.status = JobStatus.FAILED.value
                job.error = f"Invalid queued EDL v2: {exc}"
                job.finished_at = now()
                db.commit()
                return True

        temp_dir = settings.mediagrid_data_dir / "temp"
        output_dir = settings.mediagrid_data_dir / "renders"
        temp_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        attempt_id = f"{job.id}-{uuid4().hex}"
        props_path = (temp_dir / f"{attempt_id}.json").resolve()
        public_dir = (temp_dir / f"{attempt_id}-media").resolve()
        staged_output_path = (temp_dir / f"{attempt_id}.mp4").resolve()
        output_path = (output_dir / f"{project.id}.mp4").resolve()
        channel = db.get(Channel, project.channel_id)
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
        props = render_props(
            project, channel, video_tracks, overlays, sounds, video_layers
        )
        project.status = ProjectStatus.RENDERING.value
        db.commit()
        stop_heartbeat = start_lease_heartbeat(job.id, job.lease_owner)
        try:
            staged = stage_scene_assets(db, [
                *video_tracks,
                *({"asset_id": item.source_asset_id} for item in video_layers),
            ], public_dir)
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
            for item in props.get("video_layers", []):
                media = staged[item["source_asset_id"]]
                if media["media_kind"] != "video":
                    raise ValueError("Video layer asset is not an MP4")
                item["media_file"] = media["media_file"]
                duration = float(media["media_duration"])
                if item["source_out_ms"] / 1000 > duration + 0.05:
                    raise ValueError("Video layer source interval exceeds the MP4")
            if sounds:
                staged_sounds = stage_sound_assets(
                    db, {item.source_asset_id for item in sounds}, public_dir
                )
                for item in props["sounds"]:
                    item["media_file"] = staged_sounds[item["source_asset_id"]]
                    source_duration = audio_duration(public_dir / item["media_file"])
                    start = (item["source_in_ms"] or 0) / 1000
                    end = (item["source_out_ms"] or source_duration * 1000) / 1000
                    if start >= source_duration or end > source_duration + 0.05:
                        raise ValueError("Sound source interval exceeds the audio file")
                    if not item["loop"] and (end - start) * 1000 + 35 < item["duration_ms"]:
                        raise ValueError("Sound item exceeds its audio source")
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
                    "MediaGridTimelineV2" if overlays or sounds or video_layers
                    else "MediaGridVideo",
                    str(staged_output_path),
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
                    "render:v2" if overlays or sounds or video_layers else "render",
                    "--workspace",
                    "@mediagrid/renderer",
                    "--",
                    str(staged_output_path),
                    "--props",
                    str(props_path),
                ]
                browser = shutil.which("chromium") or shutil.which("google-chrome")
            if browser:
                command.append(f"--browser-executable={browser}")
            command.append(f"--public-dir={public_dir}")
            subprocess.run(command, check=True, cwd=renderer_root if renderer_root else None)
            if valid_voice is not None:
                voiced = temp_dir / f"{attempt_id}-voiced.mp4"
                ffmpeg = settings.mediagrid_ffmpeg_path or "ffmpeg"
                voice_command = [
                        str(ffmpeg),
                        "-y",
                        "-i",
                        str(staged_output_path),
                        "-i",
                        str(voice),
                        "-map",
                        "0:v:0",
                        "-c:v",
                        "copy",
                        "-c:a",
                        "aac",
                ]
                if sounds:
                    voice_command.extend([
                        "-filter_complex",
                        "[0:a:0][1:a:0]amix=inputs=2:duration=longest:normalize=0,"
                        "alimiter=limit=0.95,apad[mix]",
                        "-map", "[mix]",
                    ])
                else:
                    voice_command.extend(["-map", "1:a:0", "-af", "apad"])
                voice_command.extend(["-t", str(render_duration), str(voiced)])
                subprocess.run(
                    voice_command,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                voiced.replace(staged_output_path)
            video_info = validate_video(staged_output_path)
            job.status = JobStatus.SUCCEEDED.value
            job.progress = 1
            digest = hashlib.sha256()
            with staged_output_path.open("rb") as rendered:
                for chunk in iter(lambda: rendered.read(1024 * 1024), b""):
                    digest.update(chunk)
            job.result = {
                "output": str(output_path), "sha256": digest.hexdigest(),
                "edl_sha256": edl_sha256, **video_info,
            }
            if revision_sha256:
                job.result["revision_sha256"] = revision_sha256
            job.finished_at = now()
            project.status = ProjectStatus.QC.value
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
            stop_heartbeat()
            props_path.unlink(missing_ok=True)
            if public_dir.parent == temp_dir.resolve() and public_dir.name == f"{attempt_id}-media":
                shutil.rmtree(public_dir, ignore_errors=True)
            if not finish_render_attempt(
                db, job, project, lease_owner, staged_output_path, output_path,
            ):
                logger.warning("Render result discarded after losing job lease %s", job.id)
        return True


def media_one() -> bool:
    settings = get_settings()
    with SessionLocal() as db:
        job = claim_next_job(db, [
            "VOICE", "TRANSCRIBE", "PROXY", "ASR_WORDS", "CAPTION_RENDER",
            "CLIP_ANALYSIS", "CLIP_RENDER", "FOOTBALL_RENDER",
            "NARRATIVE_3D_RENDER",
        ])
        if job is None:
            return False
        db.commit()
        lease_owner = job.lease_owner
        stop_heartbeat = start_lease_heartbeat(job.id, job.lease_owner)
        output = None
        staged_artifact: tuple[Path, Path] | None = None
        attempt_id = f"{job.id}-{uuid4().hex}"
        staged_output = settings.mediagrid_data_dir / "temp" / f"media-{attempt_id}.mp4"
        try:
            staged_output.parent.mkdir(parents=True, exist_ok=True)
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
            elif job.job_type == "PROXY":
                asset_id = job.payload.get("asset_id")
                asset = db.get(Asset, asset_id) if asset_id else None
                if asset is None:
                    raise ValueError("Proxy asset not found")
                job.result = build_proxy(db, job, asset)
                output = settings.mediagrid_data_dir / "proxies" / f"{asset.id}.mp4"
            elif job.job_type == "ASR_WORDS":
                asset_id = job.payload.get("asset_id")
                asset = db.get(Asset, asset_id) if asset_id else None
                if asset is None:
                    raise ValueError("ASR asset not found")
                source = settings.mediagrid_data_dir / "assets" / asset.id
                if not source.is_file() or sha256_file(source) != asset.sha256:
                    raise ValueError("ASR original changed after import")
                if job.payload.get("sha256") != asset.sha256:
                    raise ValueError("ASR job source hash mismatch")
                if db.scalar(select(Transcript).where(Transcript.asset_id == asset.id)):
                    raise ValueError("Transcript already exists; human edits are preserved")
                def progress(value: float) -> None:
                    job.progress = min(0.95, 0.05 + 0.9 * value)
                    db.commit()
                words, language, version = transcribe_words(source, progress)
                cues = group_words(words)
                duration_ms, _ = probe_media(source)
                validate_timing(words, cues, duration_ms)
                db.expire_all()
                if db.scalar(select(Transcript).where(Transcript.asset_id == asset.id)):
                    raise ValueError("Transcript appeared during ASR; human edits are preserved")
                model_dir = settings.mediagrid_asr_model_dir
                if model_dir is None:
                    raise ValueError("Local ASR model disappeared during transcription")
                model_id = f"sha256:{sha256_file(model_dir / 'model.bin')}"
                transcript = Transcript(
                    asset_id=asset.id, source_sha256=asset.sha256,
                    engine="FASTER_WHISPER_CPU", model_id=model_id,
                    model_version=version, language=language, revision=1,
                    status="REVIEW_REQUIRED" if words else "NO_SPEECH_DETECTED",
                    cues_json=[cue.model_dump() for cue in cues],
                )
                db.add(transcript)
                db.flush()
                replace_words(db, transcript, words)
                job.result = {
                    "asset_id": asset.id, "transcript_id": transcript.id,
                    "source_sha256": asset.sha256, "words": len(words),
                    "cues": len(cues), "status": transcript.status,
                    "engine": transcript.engine, "model_version": version,
                    "model_id": model_id,
                }
            elif job.job_type == "CAPTION_RENDER":
                asset_id = job.payload.get("asset_id")
                asset = db.get(Asset, asset_id) if asset_id else None
                transcript = db.scalar(select(Transcript).where(Transcript.asset_id == asset_id))
                if asset is None or transcript is None:
                    raise ValueError("Caption asset or transcript not found")
                if (job.payload.get("sha256") != asset.sha256
                        or job.payload.get("revision") != transcript.revision):
                    raise ValueError("Caption source or review changed after queueing")
                staged_artifact = (staged_output, caption_output(asset.id, transcript.revision))
                job.result = burn_captions(asset, transcript, attempt_id, staged_output)
            elif job.job_type == "CLIP_ANALYSIS":
                asset_id = job.payload.get("asset_id")
                asset = db.get(Asset, asset_id) if asset_id else None
                transcript = db.scalar(select(Transcript).where(Transcript.asset_id == asset_id))
                if asset is None or transcript is None:
                    raise ValueError("Clip source or transcript not found")
                if (job.payload.get("sha256") != asset.sha256
                        or job.payload.get("transcript_revision") != transcript.revision):
                    raise ValueError("Clip source or transcript changed after queueing")
                job.result = analyze_asset(db, asset, transcript)
            elif job.job_type == "CLIP_RENDER":
                asset_id = job.payload.get("asset_id")
                candidate_id = job.payload.get("candidate_id")
                asset = db.get(Asset, asset_id) if asset_id else None
                candidate = db.get(ClipCandidate, candidate_id) if candidate_id else None
                transcript = db.scalar(select(Transcript).where(Transcript.asset_id == asset_id))
                if asset is None or transcript is None or candidate is None:
                    raise ValueError("Clip source, transcript or selection not found")
                if (job.payload.get("sha256") != asset.sha256
                        or job.payload.get("revision") != candidate.revision
                        or job.payload.get("transcript_revision") != transcript.revision):
                    raise ValueError("Clip source or human selection changed after queueing")
                staged_artifact = (staged_output, clip_output(candidate.id, candidate.revision))
                job.result = render_selected_clip(
                    asset, transcript, candidate, attempt_id, staged_output,
                )
            elif job.job_type == "FOOTBALL_RENDER":
                sequence = db.get(FootballSequence, job.payload.get("sequence_id"))
                if (sequence is None or sequence.revision != job.payload.get("revision")
                        or sequence.project_id != job.project_id):
                    raise ValueError("Football sequence changed after queueing")
                staged_artifact = (staged_output, football_output(sequence.id, sequence.revision))
                job.result = render_football(db, sequence, attempt_id, staged_output)
            elif job.job_type == "NARRATIVE_3D_RENDER":
                sequence = db.get(Narrative3D, job.payload.get("sequence_id"))
                if (sequence is None or sequence.revision != job.payload.get("revision")
                        or sequence.project_id != job.project_id
                        or story_sha256(sequence) != job.payload.get("story_sha256")
                        or sha256_file(blender_script()) != job.payload.get("rig_sha256")):
                    raise ValueError("3D story or rig changed after queueing")
                quality = job.payload.get("quality")
                if quality not in {"blocking", "final"}:
                    raise ValueError("Invalid 3D render quality")

                def progress(value: float) -> None:
                    job.progress = value
                    db.commit()

                staged_artifact = (staged_output, narrative_output(
                    sequence.id, sequence.revision, quality,
                ))
                job.result = render_narrative(
                    db, sequence, attempt_id, quality, progress, staged_output,
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
            job.result = {
                **(job.result or {}), **({"output": str(output)} if output else {}),
            }
            if staged_artifact is None:
                record_event(db, f"{job.job_type}_FINISHED", "job", job.id,
                             after=job.result)
        except (OSError, ValueError, RuntimeError, ImportError,
                subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            job.status = JobStatus.FAILED.value
            job.error = str(exc)
            if job.job_type == "PROXY":
                failed_asset = db.get(Asset, job.payload.get("asset_id"))
                if failed_asset:
                    failed_asset.metadata_json = {
                        **(failed_asset.metadata_json or {}),
                        "ingest_status": "FAILED",
                    }
            record_event(db, f"{job.job_type}_FAILED", "job", job.id, after={"error": job.error})
        finally:
            stop_heartbeat()
        job.finished_at = now()
        if staged_artifact is not None:
            if not finish_media_render_attempt(
                db, job, lease_owner, *staged_artifact,
            ):
                logger.warning("Media result discarded after losing job lease %s", job.id)
        elif fence_job_completion(db, job.id, lease_owner):
            db.commit()
        else:
            db.rollback()
            logger.warning("Media result discarded after losing job lease %s", job.id)
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
    if get_settings().mediagrid_mode != "LOCAL":
        raise RuntimeError("The local media worker cannot process server jobs directly")
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
