import argparse
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from sqlalchemy import select

from apps.api.config import get_settings
from apps.api.database import SessionLocal
from apps.api.models import Channel, Job, JobStatus, Project, ProjectStatus, now
from apps.api.services import claim_next_job, record_event


def validate_video(path: Path) -> dict[str, object]:
    result = subprocess.run(
        [
            "ffprobe",
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
            select(Job).where(Job.job_type == "RENDER", Job.status == JobStatus.RUNNING.value)
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
                job.error = "Render was interrupted and reached the retry limit"
                job.finished_at = now()
                if project:
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

        temp_dir = settings.mediagrid_data_dir / "temp"
        output_dir = settings.mediagrid_data_dir / "renders"
        temp_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        props_path = (temp_dir / f"{job.id}.json").resolve()
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
        props = {
            "title": project.title,
            "format": project.format,
            "accent": accent,
            "scenes": [
                dict(item, on_screen_text=captions.get(item["scene_id"]))
                for item in project.edl["tracks"]["video"]
            ],
        }
        props_path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
        project.status = ProjectStatus.RENDERING.value
        db.commit()
        try:
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
            subprocess.run(command, check=True)
            video_info = validate_video(output_path)
            job.status = JobStatus.SUCCEEDED.value
            job.progress = 1
            job.result = {"output": str(output_path), **video_info}
            job.finished_at = now()
            project.status = ProjectStatus.QC.value
            record_event(db, "RENDER_FINISHED", "project", project.id, after=job.result)
        except (subprocess.CalledProcessError, ValueError, OSError, json.JSONDecodeError) as exc:
            job.status = JobStatus.FAILED.value
            job.error = f"Render validation failed: {exc}"
            job.finished_at = now()
            project.status = ProjectStatus.FAILED.value
            project.error = job.error
            record_event(db, "RENDER_FAILED", "project", project.id, after={"error": job.error})
        finally:
            props_path.unlink(missing_ok=True)
            db.commit()
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="MediaGrid render worker")
    parser.add_argument("--once", action="store_true", help="Process at most one queued job")
    args = parser.parse_args()
    recover_interrupted_jobs()
    if args.once:
        render_one()
        return
    while True:
        if not render_one():
            time.sleep(2)


if __name__ == "__main__":
    main()
