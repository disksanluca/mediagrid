import argparse
import json
import shutil
import subprocess

from apps.api.config import get_settings
from apps.api.database import SessionLocal
from apps.api.models import JobStatus, Project, ProjectStatus, now
from apps.api.services import claim_next_job, record_event


def render_one() -> bool:
    settings = get_settings()
    with SessionLocal() as db:
        job = claim_next_job(db)
        if job is None:
            return False
        db.commit()
        if job.job_type != "RENDER" or not job.project_id:
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
        captions = {item["scene_id"]: item["text"] for item in project.edl["tracks"]["captions"]}
        props = {
            "title": project.title,
            "format": project.format,
            "accent": "#c6ff3d",
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
            job.status = JobStatus.SUCCEEDED.value
            job.progress = 1
            job.result = {"output": str(output_path)}
            job.finished_at = now()
            project.status = ProjectStatus.QC.value
            record_event(db, "RENDER_FINISHED", "project", project.id, after=job.result)
        except subprocess.CalledProcessError as exc:
            job.status = JobStatus.FAILED.value
            job.error = f"Renderer exited with code {exc.returncode}"
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
    parser.parse_args()
    render_one()


if __name__ == "__main__":
    main()
