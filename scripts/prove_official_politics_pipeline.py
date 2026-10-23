"""Render a chosen Câmara PL in an isolated local MediaGrid run.

This is a technical audiovisual proof. It does not approve claims, license media,
or publish a political video. Pass an explicit proposal ID; never auto-pick a story.
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
from uuid import uuid4

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def checked(response):
    if response.status_code >= 400:
        raise RuntimeError(f"API returned {response.status_code}: {response.text}")
    return response.json()


def executable(name: str, chosen: Path | None = None) -> str:
    found = str(chosen.resolve()) if chosen else shutil.which(name)
    if not found or not Path(found).is_file():
        raise RuntimeError(f"Required executable is unavailable: {name}")
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal_id", type=int, help="PL ID selected by the operator")
    parser.add_argument("--node", type=Path, help="Path to the local Node.js executable")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "rea-proof")
    args = parser.parse_args()
    if args.proposal_id <= 0:
        parser.error("proposal_id must be positive")
    node = executable("node", args.node)
    ffmpeg = executable("ffmpeg")
    ffprobe = executable("ffprobe")
    if not (ROOT / "node_modules" / "@remotion" / "cli" / "remotion-cli.js").is_file():
        raise RuntimeError("Install locked JavaScript dependencies before rendering")
    run_name = f"politics-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    run_dir = (args.output / run_name).resolve()
    run_dir.mkdir(parents=True, exist_ok=False)

    # Configure storage before importing the database or worker modules.
    os.environ.update({
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
    })
    from apps.api.local_media import voice_available

    if not voice_available():
        raise RuntimeError("Local Windows voice is unavailable; no silent substitute is allowed")
    from apps.api.main import app
    from workers.render.main import media_one, render_one

    with TestClient(app) as client:
        channel = checked(client.post("/api/v1/channels", json={
            "name": "Prova política local", "slug": "prova-politica-local",
            "niche": "Política", "default_engine": "politics",
        }))
        project = checked(client.post("/api/v1/politics/projects", json={
            "channel_id": channel["id"], "proposal_id": args.proposal_id,
        }))
        project_id = project["id"]
        plan = project["plan"]
        source_refs = plan["source_refs"]
        claims = checked(client.get(f"/api/v1/projects/{project_id}/claims"))
        if (project["content_type"] != "knowledge"
                or plan["origin"] != "OFFICIAL_SOURCE"
                or not source_refs or not claims
                or any(claim["status"] != "REVIEW_REQUIRED" for claim in claims)):
            raise RuntimeError("Official import lost its evidence or editorial gate")
        voice_job_id = checked(client.post(f"/api/v1/projects/{project_id}/voice"))["job_id"]
        if not media_one():
            raise RuntimeError("Local worker did not claim the voice job")
        voice_job = checked(client.get(f"/api/v1/jobs/{voice_job_id}"))
        if voice_job["status"] != "SUCCEEDED":
            raise RuntimeError(f"Voice job failed: {voice_job['error']}")
        render_job_id = checked(client.post(f"/api/v1/projects/{project_id}/render"))["job_id"]
        if not render_one():
            raise RuntimeError("Local worker did not claim the render job")
        render_job = checked(client.get(f"/api/v1/jobs/{render_job_id}"))
        if render_job["status"] != "SUCCEEDED":
            raise RuntimeError(f"Render job failed: {render_job['error']}")
        final_project = checked(client.get(f"/api/v1/projects/{project_id}"))
        if final_project["status"] != "QC":
            raise RuntimeError(f"Expected editorial QC, got {final_project['status']}")
        review = client.post(f"/api/v1/projects/{project_id}/review", json={
            "source_urls": [source_refs[0]["url"]],
            "facts_confirmed": True, "rights_confirmed": True,
            "notes": "Technical proof cannot approve unreviewed claims",
        })
        if review.status_code != 409 or client.get(
            f"/api/v1/projects/{project_id}/export"
        ).status_code != 409:
            raise RuntimeError("Political export was available without claim review")

    video = run_dir / "renders" / f"{project_id}.mp4"
    voice = run_dir / "voice" / f"{project_id}.wav"
    if not video.is_file() or not voice.is_file():
        raise RuntimeError("A declared successful job is missing its output")
    with wave.open(str(voice), "rb") as wav:
        voice_duration = wav.getnframes() / wav.getframerate()
    probe = json.loads(subprocess.run([
        ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(video),
    ], capture_output=True, text=True, check=True).stdout)
    visual = next((item for item in probe["streams"] if item["codec_type"] == "video"), None)
    audio = next((item for item in probe["streams"] if item["codec_type"] == "audio"), None)
    duration = float(probe["format"]["duration"])
    if (not visual or not audio or visual["codec_name"] != "h264"
            or audio["codec_name"] != "aac"
            or (visual["width"], visual["height"]) != (1080, 1920)
            or duration + 0.05 < voice_duration):
        raise RuntimeError("Rendered MP4 failed the vertical H.264/AAC/voice acceptance checks")
    video_sha = hashlib.sha256(video.read_bytes()).hexdigest()
    if render_job["result"].get("sha256") != video_sha:
        raise RuntimeError("Worker-reported video hash does not match the file")
    evidence = {
        "kind": "technical_proof_not_editorial_approval",
        "proposal_id": args.proposal_id,
        "project_id": project_id,
        "project_status": final_project["status"],
        "plan_origin": plan["origin"],
        "source_refs": source_refs,
        "claim_count_pending": len(claims),
        "voice_job_id": voice_job_id,
        "voice_job_status": voice_job["status"],
        "render_job_id": render_job_id,
        "render_job_status": render_job["status"],
        "video_path": str(video),
        "video_sha256": video_sha,
        "video_duration_seconds": duration,
        "voice_duration_seconds": voice_duration,
        "video_codec": visual["codec_name"],
        "audio_codec": audio["codec_name"],
        "width": visual["width"],
        "height": visual["height"],
        "review_without_claim_approval_status": review.status_code,
    }
    (run_dir / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
