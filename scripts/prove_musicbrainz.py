"""Render a source-backed music metadata draft in an isolated local workspace.

The MusicBrainz API is queried live. This script never fetches album covers,
music recordings or samples and never approves or publishes the project.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

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
    parser.add_argument("release_group_id", type=UUID)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "music-proof")
    parser.add_argument("--scheduled", action="store_true",
                        help="Wait for a real local schedule before rendering the draft")
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
        "ALLOW_PAID_AI": "false", "DRY_RUN": "true",
        "OLLAMA_BASE_URL": "http://127.0.0.1:1",
    })

    from apps.api.local_media import voice_available
    from apps.api.main import app
    from apps.api.official_music import fetch_release_group
    from workers.render.main import media_one, render_one
    from workers.render.scheduled_music import draft_one

    if not voice_available():
        raise RuntimeError("Windows speech synthesis is unavailable")
    source, _ = fetch_release_group(args.release_group_id)
    snapshot = {key: source[key] for key in (
        "id", "title", "artist", "first_release_date", "primary_type",
    )}
    source_digest = hashlib.sha256(json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    (run_dir / "source.json").write_text(json.dumps(
        snapshot, ensure_ascii=False, indent=2,
    ), encoding="utf-8")
    with TestClient(app) as client:
        channel = checked(client.post("/api/v1/channels", json={
            "name": "Prova editorial Música", "slug": "prova-musica",
            "niche": "Música", "default_engine": "music",
        }))
        schedule_id = None
        scheduled_state = None
        if args.scheduled:
            due_at = datetime.now(UTC) + timedelta(seconds=12)
            schedule = checked(client.post("/api/v1/music/drafts/schedules", json={
                "channel_id": channel["id"],
                "release_group_id": str(args.release_group_id),
                "scheduled_at": due_at.isoformat(),
            }))
            schedule_id = schedule["id"]
            if draft_one():
                raise RuntimeError("A future draft was created before its scheduled time")
            time.sleep(max(0, (due_at - datetime.now(UTC)).total_seconds() + 0.2))
            if not draft_one():
                raise RuntimeError("Local worker did not claim the due music draft")
            completed = next(item for item in checked(client.get(
                "/api/v1/music/drafts/schedules"
            )) if item["id"] == schedule_id)
            if completed["status"] != "SUCCEEDED" or not completed["project_id"]:
                raise RuntimeError(f"Scheduled draft failed: {completed}")
            scheduled_state = completed
            project = checked(client.get(
                f"/api/v1/projects/{completed['project_id']}"
            ))
        else:
            project = checked(client.post("/api/v1/music/projects", json={
                "channel_id": channel["id"], "release_group_id": str(args.release_group_id),
            }))
        project_id = project["id"]
        plan = project["plan"]
        if plan["source_refs"][0]["snapshot_sha256"] != source_digest:
            raise RuntimeError("MusicBrainz record changed between proof fetch and import")
        claims = checked(client.get(f"/api/v1/projects/{project_id}/claims"))
        if (plan["origin"] != "OFFICIAL_SOURCE" or len(plan["scenes"]) != 3
                or len(claims) != 3 or any(
                    claim["status"] != "REVIEW_REQUIRED" for claim in claims
                )):
            raise RuntimeError("Music draft or factual review ledger is incomplete")
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
        served = client.get(f"/api/v1/projects/{project_id}/output")
        digest = render["result"]["sha256"]
        if (project["status"] != "QC" or served.status_code != 200
                or served.headers.get("etag") != digest
                or hashlib.sha256(served.content).hexdigest() != digest):
            raise RuntimeError("Music MP4 is not a verified QC artifact")
        if client.get(f"/api/v1/projects/{project_id}/export").status_code != 409:
            raise RuntimeError("Unreviewed music draft unexpectedly became exportable")

    output = run_dir / "renders" / f"{project_id}.mp4"
    probe = subprocess.run([
        ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(output),
    ], check=True, capture_output=True, text=True)
    media = json.loads(probe.stdout)
    video = next((item for item in media["streams"] if item["codec_type"] == "video"), None)
    audio = next((item for item in media["streams"] if item["codec_type"] == "audio"), None)
    if (not video or not audio or video["codec_name"] != "h264"
            or audio["codec_name"] != "aac"
            or (video["width"], video["height"]) != (1080, 1920)):
        raise RuntimeError("Music draft is not a vertical H.264/AAC MP4")
    evidence = {
        "release_group_id": str(args.release_group_id), "source_url": source["source_url"],
        "source_record_sha256": source_digest, "project_id": project_id,
        "plan_origin": plan["origin"], "scene_count": len(plan["scenes"]),
        "claims_review_required": len(claims), "voice_job": voice["status"],
        "render_job": render["status"], "project_status": project["status"],
        "export_blocked": True, "human_approved": False, "published": False,
        "video": str(output), "sha256": digest,
        "duration_seconds": float(media["format"]["duration"]),
        "width": video["width"], "height": video["height"],
        "video_codec": video["codec_name"], "audio_codec": audio["codec_name"],
        "paid_ai_enabled": False, "scheduled": args.scheduled,
        "schedule_id": schedule_id,
        "scheduled_at": scheduled_state["scheduled_at"] if scheduled_state else None,
        "schedule_status": scheduled_state["status"] if scheduled_state else None,
        "schedule_attempts": scheduled_state["attempt"] if scheduled_state else None,
    }
    (run_dir / "evidence.json").write_text(json.dumps(
        evidence, ensure_ascii=False, indent=2,
    ), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
