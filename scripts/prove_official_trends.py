"""Render a sourced Wikimedia Trends draft without approving or publishing it."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def checked(response):
    if response.status_code >= 400:
        raise RuntimeError(f"API returned {response.status_code}: {response.text}")
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", type=date.fromisoformat, default=date(2026, 10, 20))
    parser.add_argument("--article", default="Benito_di_Paula")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "trends-proof")
    args = parser.parse_args()
    run_dir = (args.output / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")).resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    tools = {name: shutil.which(name) for name in ("node", "ffmpeg", "ffprobe")}
    if not all(tools.values()):
        raise RuntimeError(f"Missing executables: {tools}")
    if not (ROOT / "node_modules" / "@remotion" / "cli" / "remotion-cli.js").is_file():
        raise RuntimeError("Locked JavaScript dependencies are not installed")
    os.environ.update({
        "DATABASE_URL": f"sqlite:///{(run_dir / 'mediagrid.db').as_posix()}",
        "MEDIAGRID_DATA_DIR": str(run_dir),
        "MEDIAGRID_MODE": "LOCAL",
        "MEDIAGRID_RENDERER_ROOT": str(ROOT / "apps" / "renderer"),
        "MEDIAGRID_NODE_PATH": str(tools["node"]),
        "MEDIAGRID_FFMPEG_PATH": str(tools["ffmpeg"]),
        "MEDIAGRID_FFPROBE_PATH": str(tools["ffprobe"]),
        "ALLOW_PAID_AI": "false",
        "DRY_RUN": "true",
        "OLLAMA_BASE_URL": "http://127.0.0.1:1",
    })

    from apps.api.local_media import voice_available
    from apps.api.main import app
    from apps.api.official_trends import fetch_top
    from workers.render.main import media_one, render_one

    if not voice_available():
        raise RuntimeError("Windows speech synthesis is unavailable")
    records, fetched_at = fetch_top(args.day)
    page = next((item for item in records if item["article"] == args.article), None)
    if page is None:
        raise RuntimeError("Chosen page is not in that day's Wikimedia top list")
    snapshot = {
        "project": "pt.wikipedia", "access": "all-access", "day": args.day.isoformat(),
        "article": page["article"], "views": page["views"], "rank": page["rank"],
    }
    digest = hashlib.sha256(json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    (run_dir / "source.json").write_text(json.dumps({
        "snapshot": snapshot, "url": page["source_url"],
        "fetched_at": fetched_at.isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    with TestClient(app) as client:
        channel = checked(client.post("/api/v1/channels", json={
            "name": "Prova editorial Trends", "slug": "prova-trends",
            "niche": "Tendências", "default_engine": "trends",
        }))
        project = checked(client.post("/api/v1/trends/projects", json={
            "channel_id": channel["id"], "day": args.day.isoformat(),
            "article": args.article,
        }))
        project_id = project["id"]
        plan = project["plan"]
        if plan["source_refs"][0]["snapshot_sha256"] != digest:
            raise RuntimeError("Wikimedia record changed between proof fetch and import")
        claims = checked(client.get(f"/api/v1/projects/{project_id}/claims"))
        if (project["content_type"] != "knowledge" or len(claims) != len(plan["scenes"])
                or any(claim["status"] != "REVIEW_REQUIRED" for claim in claims)):
            raise RuntimeError("Trends claim ledger is incomplete")
        voice_id = checked(client.post(f"/api/v1/projects/{project_id}/voice"))["job_id"]
        if not media_one():
            raise RuntimeError("Voice worker did not claim the job")
        voice = checked(client.get(f"/api/v1/jobs/{voice_id}"))
        if voice["status"] != "SUCCEEDED":
            raise RuntimeError(f"Voice failed: {voice['error']}")
        render_id = checked(client.post(f"/api/v1/projects/{project_id}/render"))["job_id"]
        if not render_one():
            raise RuntimeError("Render worker did not claim the job")
        render = checked(client.get(f"/api/v1/jobs/{render_id}"))
        if render["status"] != "SUCCEEDED":
            raise RuntimeError(
                f"Render not complete: status={render['status']}, "
                f"attempt={render['attempt']}, error={render['error']}"
            )
        project = checked(client.get(f"/api/v1/projects/{project_id}"))
        served = client.get(f"/api/v1/projects/{project_id}/output")
        video_digest = render["result"]["sha256"]
        if (project["status"] != "QC" or served.status_code != 200
                or served.headers.get("etag") != video_digest
                or hashlib.sha256(served.content).hexdigest() != video_digest
                or client.get(f"/api/v1/projects/{project_id}/export").status_code != 409):
            raise RuntimeError("Trends draft is not a verified, export-blocked QC artifact")

    output = run_dir / "renders" / f"{project_id}.mp4"
    probe = subprocess.run([
        str(tools["ffprobe"]), "-v", "error", "-show_format", "-show_streams",
        "-of", "json", str(output),
    ], check=True, capture_output=True, text=True)
    media = json.loads(probe.stdout)
    video = next((item for item in media["streams"] if item["codec_type"] == "video"), None)
    audio = next((item for item in media["streams"] if item["codec_type"] == "audio"), None)
    if (not video or not audio or video["codec_name"] != "h264"
            or audio["codec_name"] != "aac"
            or (video["width"], video["height"]) != (1080, 1920)):
        raise RuntimeError("Trends draft is not a vertical H.264/AAC MP4")
    evidence = {
        "day": args.day.isoformat(), "article": args.article,
        "source_url": page["source_url"], "source_snapshot_sha256": digest,
        "project_id": project_id, "claims_review_required": len(claims),
        "voice_job": voice["status"], "render_job": render["status"],
        "project_status": project["status"], "export_blocked": True,
        "human_approved": False, "published": False,
        "video": str(output), "sha256": video_digest,
        "duration_seconds": float(media["format"]["duration"]),
        "width": video["width"], "height": video["height"],
        "video_codec": video["codec_name"], "audio_codec": audio["codec_name"],
        "paid_ai_enabled": False,
    }
    (run_dir / "evidence.json").write_text(json.dumps(
        evidence, ensure_ascii=False, indent=2,
    ), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
