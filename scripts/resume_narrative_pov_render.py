"""Resume only the M4 render/QA phase of an isolated Narrative POV proof run."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def checked(response):
    if response.status_code >= 400:
        raise RuntimeError(f"{response.status_code}: {response.text}")
    return response.json()


def run(command, *, timeout=1800):
    started = time.monotonic()
    result = subprocess.run(
        [str(item) for item in command], check=True, capture_output=True, text=True,
        timeout=timeout,
    )
    return result, round((time.monotonic() - started) * 1000)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    base = (ROOT / "data/narrative-pov-proof").resolve()
    folder = (base / args.run).resolve()
    if not folder.is_dir() or folder == base or not folder.is_relative_to(base):
        parser.error("An existing isolated proof run is required")
    database = folder / "workspace.db"
    mix = folder / "media/narrative-mix.wav"
    narration = folder / "media/narration.wav"
    if not database.is_file() or not mix.is_file() or not narration.is_file():
        parser.error("The proof database and audio outputs must already exist")
    os.environ.update({
        "DATABASE_URL": "sqlite:///" + database.as_posix(),
        "MEDIAGRID_DATA_DIR": str(folder), "MEDIAGRID_MODE": "LOCAL",
        "MEDIAGRID_RENDERER_ROOT": str(ROOT / "apps/renderer"),
        "MEDIAGRID_NODE_PATH": shutil.which("node") or "",
        "MEDIAGRID_RENDER_CONCURRENCY": "1", "DRY_RUN": "true",
    })

    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from apps.api.config import get_settings
    from apps.api.database import SessionLocal
    from apps.api.main import app
    from apps.api.models import Asset, Job, Project
    from workers.render.main import media_one

    with SessionLocal() as db:
        project = db.scalar(select(Project).where(
            Project.title == "O celular usado que ensinou Caio a negociar"
        ))
        asset = db.scalar(select(Asset).where(Asset.name == "narrative-mix.wav"))
        if project is None or asset is None:
            raise RuntimeError("Disposable proof project or audio asset is missing")
        project_id, asset_id = project.id, asset.id

    media = folder / "media"
    with TestClient(app) as client:
        root = f"/api/v1/projects/{project_id}/creative"
        review = checked(client.get(root + "/review"))
        storyboard = checked(client.get(root + "/storyboard"))
        if review["status"] != "APPROVED_STORYBOARD" or review["blockers"]:
            raise RuntimeError("The isolated storyboard approval is not current")
        recipes = checked(client.get("/api/v1/creative/motion/recipes"))["recipes"]
        recipe = next(
            item for item in recipes
            if item["id"] == "pov.webtoon-cutout" and item["version"] == "1.3.0"
        )
        request = {
            "expected_storyboard_revision": storyboard["revision"],
            "expected_snapshot_sha256": review["current_snapshot_sha256"],
            "recipe": {field: recipe[field] for field in ("id", "version", "sha256")},
            "asset_bindings": {"mix": asset_id}, "quality": "final",
        }
        preview = checked(client.post(root + "/motion/engine/preview", json=request))
        write(folder / "preview.json", preview)
        started = time.monotonic()
        render_job = checked(client.post(root + "/motion/engine/render", json=request))
        if not media_one():
            raise RuntimeError("M4 worker did not claim the narrative render")
        rendered = checked(client.get(f"/api/v1/jobs/{render_job['id']}"))
        render_ms = round((time.monotonic() - started) * 1000)
        write(folder / "render-job.json", rendered)
        if rendered["status"] != "SUCCEEDED":
            raise RuntimeError(rendered["error"])
        video = media / "narrative-pov-studio.mp4"
        shutil.copyfile(rendered["result"]["output"], video)
        artifact = checked(client.post(
            root + f"/motion/jobs/{rendered['id']}/review",
            json={
                "expected_revision": 0,
                "expected_plan_sha256": preview["plan_sha256"],
                "expected_video_sha256": rendered["result"]["sha256"],
                "decision": "REQUEST_REVIEW",
                "notes": (
                    "Illustrated cutout POV with local narration; human visual and "
                    "listening review remains required."
                ),
            },
        ))
        write(folder / "artifact-review.json", artifact)

    ffmpeg = str(get_settings().mediagrid_ffmpeg_path or "ffmpeg")
    ffprobe = str(get_settings().mediagrid_ffprobe_path or "ffprobe")
    probe_result, _ = run([
        ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", video,
    ])
    (media / "ffprobe.json").write_text(probe_result.stdout, encoding="utf-8")
    run([ffmpeg, "-v", "error", "-i", video, "-f", "null", "NUL"])
    frames = media / "frames"
    frames.mkdir(exist_ok=True)
    for index in range(8):
        run([
            ffmpeg, "-v", "error", "-ss", str(index * 7 + 3.5), "-i", video,
            "-frames:v", "1", "-y", frames / f"scene-{index + 1:02d}.png",
        ])
    run([
        ffmpeg, "-v", "error", "-i", video, "-vf",
        "fps=1/7,scale=270:480,tile=4x2", "-frames:v", "1", "-y",
        media / "contact-sheet.png",
    ])

    with SessionLocal() as db:
        agent_jobs = db.scalars(select(Job).where(
            Job.project_id == project_id, Job.job_type == "CREATIVE_AI"
        ).order_by(Job.created_at)).all()
    agent_metrics = {}
    for job in agent_jobs:
        task = (job.payload or {}).get("task", job.id)
        result = job.result or {}
        agent_metrics[task] = {
            "job_id": job.id, "status": job.status, "provider": result.get("provider"),
            "latency_ms": result.get("latency_ms"), "repairs": result.get("repair_count"),
            "resources_before": result.get("resources_before"),
            "resources_after": result.get("resources_after"),
        }
    fixture = ROOT / "tests/fixtures/narrative_pov_editorial.json"
    storyboard_file = folder / "storyboard-used.json"
    proof = {
        "finished_at": time.time(), "project_id": project_id,
        "editorial_source": json.loads(fixture.read_text(encoding="utf-8"))["provenance"],
        "agents": agent_metrics,
        "m4_render": {"job_id": render_job["id"], "wall_ms": render_ms},
        "video_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
        "narration_sha256": hashlib.sha256(narration.read_bytes()).hexdigest(),
        "mix_sha256": hashlib.sha256(mix.read_bytes()).hexdigest(),
        "storyboard_sha256": hashlib.sha256(storyboard_file.read_bytes()).hexdigest(),
        "recipe": request["recipe"], "plan_sha256": preview["plan_sha256"],
        "artifact_status": "REQUEST_REVIEW", "publication_enabled": False,
    }
    write(folder / "proof.json", proof)
    print(json.dumps({
        "video": str(video), "sha256": proof["video_sha256"],
        "contact_sheet": str(media / "contact-sheet.png"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
