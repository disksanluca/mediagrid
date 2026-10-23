"""Render a source-backed political draft in an isolated local workspace.

The Câmara API is queried live. The resulting MP4 stays in QC: this script
never approves claims, approves the project, or publishes anything.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def checked(response):
    if response.status_code >= 400:
        raise RuntimeError(f"API returned {response.status_code}: {response.text}")
    return response.json()


def executable(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"Missing required executable: {name}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal-id", type=int, default=2648811)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "politics-proof")
    args = parser.parse_args()
    run_dir = (args.output / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")).resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    node, ffmpeg, ffprobe = (executable(name) for name in ("node", "ffmpeg", "ffprobe"))
    if not (ROOT / "node_modules" / "@remotion" / "cli" / "remotion-cli.js").is_file():
        raise RuntimeError("Locked JavaScript dependencies are not installed")
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
    from apps.api.main import app
    from apps.api.official_politics import fetch_proposal
    from workers.render.main import media_one, render_one

    if not voice_available():
        raise RuntimeError("Windows speech synthesis is unavailable")
    proposal, status = fetch_proposal(args.proposal_id)
    (run_dir / "source.json").write_text(json.dumps(
        {"proposal": proposal, "status": status}, ensure_ascii=False, indent=2,
    ), encoding="utf-8")
    with TestClient(app) as client:
        channel = checked(client.post("/api/v1/channels", json={
            "name": "Prova editorial Política", "slug": "prova-politica",
            "niche": "Política", "default_engine": "politics",
        }))
        project = checked(client.post("/api/v1/politics/projects", json={
            "channel_id": channel["id"], "proposal_id": args.proposal_id,
        }))
        project_id = project["id"]
        plan = project["plan"]
        claims = checked(client.get(f"/api/v1/projects/{project_id}/claims"))
        if (plan["origin"] != "OFFICIAL_SOURCE" or len(plan["scenes"]) < 3
                or len(claims) < 2 or any(
                    claim["status"] != "REVIEW_REQUIRED" for claim in claims
                )):
            raise RuntimeError("Official draft or factual review ledger is incomplete")
        voice_job = checked(client.post(f"/api/v1/projects/{project_id}/voice"))["job_id"]
        if not media_one():
            raise RuntimeError("Voice worker did not claim the job")
        voice = checked(client.get(f"/api/v1/jobs/{voice_job}"))
        if voice["status"] != "SUCCEEDED":
            raise RuntimeError(f"Voice failed: {voice['error']}")
        render_job = checked(client.post(f"/api/v1/projects/{project_id}/render"))["job_id"]
        if not render_one():
            raise RuntimeError("Render worker did not claim the job")
        render = checked(client.get(f"/api/v1/jobs/{render_job}"))
        if render["status"] != "SUCCEEDED":
            raise RuntimeError(f"Render failed: {render['error']}")
        project = checked(client.get(f"/api/v1/projects/{project_id}"))
        served = client.get(f"/api/v1/projects/{project_id}/output")
        digest = render["result"]["sha256"]
        if (project["status"] != "QC" or served.status_code != 200
                or served.headers.get("etag") != digest
                or hashlib.sha256(served.content).hexdigest() != digest):
            raise RuntimeError("Draft MP4 is not a verified QC artifact")
        if client.get(f"/api/v1/projects/{project_id}/export").status_code != 409:
            raise RuntimeError("Unreviewed political draft unexpectedly became exportable")

    output = run_dir / "renders" / f"{project_id}.mp4"
    probe = subprocess.run([
        ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(output),
    ], check=True, capture_output=True, text=True)
    media = json.loads(probe.stdout)
    streams = media["streams"]
    video = next((item for item in streams if item["codec_type"] == "video"), None)
    audio = next((item for item in streams if item["codec_type"] == "audio"), None)
    if (not video or not audio or video["codec_name"] != "h264"
            or audio["codec_name"] != "aac" or (video["width"], video["height"]) != (1080, 1920)):
        raise RuntimeError("Official draft is not a vertical H.264/AAC MP4")
    evidence = {
        "proposal_id": args.proposal_id,
        "source_url": proposal["source_url"],
        "source_record_sha256": hashlib.sha256((run_dir / "source.json").read_bytes()).hexdigest(),
        "project_id": project_id,
        "plan_origin": plan["origin"],
        "scene_count": len(plan["scenes"]),
        "claims_review_required": len(claims),
        "voice_job": voice["status"],
        "render_job": render["status"],
        "project_status": project["status"],
        "export_blocked": True,
        "human_approved": False,
        "published": False,
        "video": str(output),
        "sha256": digest,
        "duration_seconds": float(media["format"]["duration"]),
        "width": video["width"], "height": video["height"],
        "video_codec": video["codec_name"], "audio_codec": audio["codec_name"],
        "paid_ai_enabled": False,
    }
    (run_dir / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
