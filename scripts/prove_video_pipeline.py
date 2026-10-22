"""Run the existing API and workers against an isolated local SQLite database.

This is a reproducible technical proof, not an editorial approval or publisher.
It requires the Windows speech voice, FFmpeg, Node and installed Remotion deps.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import wave
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BRIEF = (
    "Este é um teste local do MediaGrid, criado sem chamadas a serviços pagos.\n"
    "O roteiro foi salvo em cenas editáveis, com texto visível em cada trecho.\n"
    "A voz foi sintetizada neste computador e o vídeo foi montado pelo renderizador.\n"
    "O resultado precisa de revisão humana antes de qualquer uso ou publicação."
)


def require_executable(name: str) -> str:
    value = shutil.which(name)
    if not value:
        raise RuntimeError(f"Required executable is unavailable: {name}")
    return value


def checked(response):
    if response.status_code >= 400:
        raise RuntimeError(f"API returned {response.status_code}: {response.text}")
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "rea-proof")
    args = parser.parse_args()
    run_dir = (args.output / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")).resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    node = require_executable("node")
    ffmpeg = require_executable("ffmpeg")
    ffprobe = require_executable("ffprobe")
    if not (ROOT / "node_modules" / "@remotion" / "cli" / "remotion-cli.js").is_file():
        raise RuntimeError("Install the locked JavaScript dependencies before running the proof")

    # Configuration must precede imports of database.py and the worker.
    os.environ.update(
        {
            "DATABASE_URL": f"sqlite:///{(run_dir / 'mediagrid.db').as_posix()}",
            "MEDIAGRID_DATA_DIR": str(run_dir),
            "MEDIAGRID_MODE": "LOCAL",
            "MEDIAGRID_RENDERER_ROOT": str(ROOT / "apps" / "renderer"),
            "MEDIAGRID_NODE_PATH": node,
            "MEDIAGRID_FFMPEG_PATH": ffmpeg,
            "MEDIAGRID_FFPROBE_PATH": ffprobe,
            "ALLOW_PAID_AI": "false",
            "DRY_RUN": "true",
            "OLLAMA_BASE_URL": "http://127.0.0.1:1",
        }
    )
    from apps.api.local_media import voice_available

    if not voice_available():
        raise RuntimeError("Windows speech synthesis is unavailable; no fake audio will be used")

    from apps.api.database import SessionLocal
    from apps.api.main import app
    from apps.api.models import Event, Job, Project
    from workers.render.main import media_one, render_one

    with TestClient(app) as client:
        channel = checked(
            client.post(
                "/api/v1/channels",
                json={
                    "name": "Prova Local MediaGrid",
                    "slug": "prova-local",
                    "niche": "Demonstração técnica",
                    "default_engine": "clips",
                },
            )
        )
        project = checked(
            client.post(
                "/api/v1/projects",
                json={
                    "channel_id": channel["id"],
                    "title": "Fluxo local auditável",
                    "topic": BRIEF,
                    "format": "vertical",
                },
            )
        )
        project_id = project["id"]
        plan = checked(client.post(f"/api/v1/projects/{project_id}/plan"))
        if plan["origin"] != "BRIEF_BASED" or len(plan["scenes"]) != 4:
            raise RuntimeError("Brief was not converted into the expected editable scenes")
        voice_job = checked(client.post(f"/api/v1/projects/{project_id}/voice"))["job_id"]
        if not media_one():
            raise RuntimeError("Worker did not process the voice job")
        voice_result = checked(client.get(f"/api/v1/jobs/{voice_job}"))
        if voice_result["status"] != "SUCCEEDED":
            raise RuntimeError(f"Voice job failed: {voice_result['error']}")
        render_job = checked(client.post(f"/api/v1/projects/{project_id}/render"))["job_id"]
        if not render_one():
            raise RuntimeError("Worker did not process the render job")
        render_result = checked(client.get(f"/api/v1/jobs/{render_job}"))
        if render_result["status"] != "SUCCEEDED":
            raise RuntimeError(f"Render job failed: {render_result['error']}")
        final_project = checked(client.get(f"/api/v1/projects/{project_id}"))
        if final_project["status"] != "QC":
            raise RuntimeError(f"Expected QC, got {final_project['status']}")

    video = run_dir / "renders" / f"{project_id}.mp4"
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(video)],
        capture_output=True,
        text=True,
        check=True,
    )
    media = json.loads(probe.stdout)
    streams = media["streams"]
    video_stream = next((s for s in streams if s["codec_type"] == "video"), None)
    audio_stream = next((s for s in streams if s["codec_type"] == "audio"), None)
    duration = float(media["format"]["duration"])
    if not video_stream or not audio_stream:
        raise RuntimeError("MP4 does not contain both video and audio")
    if video_stream["codec_name"] != "h264" or audio_stream["codec_name"] != "aac":
        raise RuntimeError("MP4 does not use the required H.264/AAC codecs")
    if (video_stream["width"], video_stream["height"]) != (1080, 1920):
        raise RuntimeError("MP4 is not 1080x1920")
    if not 30 <= duration <= 60:
        raise RuntimeError(f"MP4 duration {duration:.2f}s is outside 30-60s")
    voice_file = run_dir / "voice" / f"{project_id}.wav"
    with wave.open(str(voice_file), "rb") as wav:
        voice_duration = wav.getnframes() / wav.getframerate()
    if duration < voice_duration:
        raise RuntimeError("The rendered MP4 is shorter than the complete narration")

    with SessionLocal() as db:
        events = list(db.scalars(select(Event).order_by(Event.created_at)))
        jobs = list(db.scalars(select(Job).order_by(Job.created_at)))
        stored = db.get(Project, project_id)
        if not stored or not stored.edl:
            raise RuntimeError("Project/EDL was not persisted")
        if len(stored.edl["tracks"]["captions"]) != len(stored.edl["tracks"]["video"]):
            raise RuntimeError("Every scene must have a persisted visual text card")
        evidence = {
            "project_id": project_id,
            "project_status": stored.status,
            "plan_origin": stored.plan["origin"],
            "edl_version": stored.edl["version"],
            "scene_count": len(stored.edl["tracks"]["video"]),
            "caption_mode": "one visual text card per scene; word timing not implemented",
            "jobs": [
                {"type": job.job_type, "status": job.status, "attempt": job.attempt}
                for job in jobs
            ],
            "events": [event.event_type for event in events],
            "video": str(video),
            "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
            "duration_seconds": duration,
            "voice_duration_seconds": voice_duration,
            "video_codec": video_stream["codec_name"],
            "audio_codec": audio_stream["codec_name"],
            "width": video_stream["width"],
            "height": video_stream["height"],
            "paid_ai_enabled": False,
            "human_approved": False,
            "published": False,
        }
    manifest = run_dir / "evidence.json"
    manifest.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
