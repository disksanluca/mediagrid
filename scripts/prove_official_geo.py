"""Import live IBGE data and render an unapproved Geo MP4 in isolated local data."""

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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--municipality-id", type=int, default=3550308)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "geo-proof")
    args = parser.parse_args()
    run_dir = (args.output / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")).resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    executables = {name: shutil.which(name) for name in ("node", "ffmpeg", "ffprobe")}
    if not all(executables.values()):
        raise RuntimeError(f"Missing executables: {executables}")
    if not (ROOT / "node_modules" / "@remotion" / "cli" / "remotion-cli.js").is_file():
        raise RuntimeError("Locked JavaScript dependencies are not installed")
    os.environ.update({
        "DATABASE_URL": f"sqlite:///{(run_dir / 'mediagrid.db').as_posix()}",
        "MEDIAGRID_DATA_DIR": str(run_dir),
        "MEDIAGRID_MODE": "LOCAL",
        "MEDIAGRID_RENDERER_ROOT": str(ROOT / "apps" / "renderer"),
        "MEDIAGRID_NODE_PATH": str(executables["node"]),
        "MEDIAGRID_FFMPEG_PATH": str(executables["ffmpeg"]),
        "MEDIAGRID_FFPROBE_PATH": str(executables["ffprobe"]),
        "ALLOW_PAID_AI": "false",
        "DRY_RUN": "true",
        "OLLAMA_BASE_URL": "http://127.0.0.1:1",
    })

    from apps.api.local_media import voice_available
    from apps.api.main import app
    from apps.api.official_geo import fetch_municipality
    from workers.render.main import media_one, render_one

    if not voice_available():
        raise RuntimeError("Windows speech synthesis is unavailable")
    source = fetch_municipality(args.municipality_id)
    snapshot = {key: source[key] for key in (
        "id", "name", "state_code", "state_name", "region_name",
        "immediate_name", "intermediate_name",
    )}
    source_digest = hashlib.sha256(json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    (run_dir / "source.json").write_text(json.dumps(
        {"snapshot": snapshot, "url": source["source_url"]},
        ensure_ascii=False, indent=2,
    ), encoding="utf-8")
    with TestClient(app) as client:
        channel = checked(client.post("/api/v1/channels", json={
            "name": "Prova editorial Geo", "slug": "prova-geo",
            "niche": "Geografia", "default_engine": "geo",
        }))
        project = checked(client.post("/api/v1/geo/projects", json={
            "channel_id": channel["id"], "municipality_id": args.municipality_id,
        }))
        project_id = project["id"]
        plan = project["plan"]
        if plan["source_refs"][0]["snapshot_sha256"] != source_digest:
            raise RuntimeError("IBGE record changed between proof fetch and project import")
        claims = checked(client.get(f"/api/v1/projects/{project_id}/claims"))
        if (project["content_type"] != "knowledge" or len(claims) != len(plan["scenes"])
                or any(claim["status"] != "REVIEW_REQUIRED" or claim["published_at"] is not None
                       or not claim["source_checked_at"] for claim in claims)):
            raise RuntimeError("Geo claim ledger is incomplete")
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
            raise RuntimeError(f"Render failed: {render['error']}")
        project = checked(client.get(f"/api/v1/projects/{project_id}"))
        output_response = client.get(f"/api/v1/projects/{project_id}/output")
        digest = render["result"]["sha256"]
        if (project["status"] != "QC" or output_response.status_code != 200
                or output_response.headers.get("etag") != digest
                or hashlib.sha256(output_response.content).hexdigest() != digest
                or client.get(f"/api/v1/projects/{project_id}/export").status_code != 409):
            raise RuntimeError("Geo draft is not a verified, export-blocked QC artifact")

    output = run_dir / "renders" / f"{project_id}.mp4"
    probe = subprocess.run([
        str(executables["ffprobe"]), "-v", "error", "-show_format", "-show_streams",
        "-of", "json", str(output),
    ], check=True, capture_output=True, text=True)
    media = json.loads(probe.stdout)
    video = next((stream for stream in media["streams"]
                  if stream["codec_type"] == "video"), None)
    audio = next((stream for stream in media["streams"]
                  if stream["codec_type"] == "audio"), None)
    if (not video or not audio or video["codec_name"] != "h264"
            or audio["codec_name"] != "aac"
            or (video["width"], video["height"]) != (1080, 1920)):
        raise RuntimeError("Geo draft is not a vertical H.264/AAC MP4")
    evidence = {
        "municipality_id": args.municipality_id,
        "source_url": source["source_url"],
        "source_snapshot_sha256": source_digest,
        "project_id": project_id,
        "claims_review_required": len(claims),
        "voice_job": voice["status"], "render_job": render["status"],
        "project_status": project["status"], "export_blocked": True,
        "human_approved": False, "published": False,
        "video": str(output), "sha256": digest,
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
