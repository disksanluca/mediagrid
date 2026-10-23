"""Manual football events reach an approved, hashed MP4 without event detection."""

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.ingestion import sha256_file
from workers.render.main import media_one


def synthetic_football(path: Path) -> Path:
    subprocess.run([
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30:d=5",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
        "-shortest", str(path),
    ], check=True, timeout=120)
    return path


def test_football_sequence_requires_review_and_renders_real_replay(
    client: TestClient, tmp_path: Path
) -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg/FFprobe unavailable before CI installs the desktop runtime")
    source = synthetic_football(tmp_path / "own-football.mp4")
    with source.open("rb") as media:
        asset = client.post("/api/v1/assets", files={
            "file": ("own-football.mp4", media, "video/mp4"),
        }, data={"rights_status": "OWNED", "creator": "synthetic test"})
    assert asset.status_code == 201, asset.text
    asset_id = asset.json()["id"]
    channel = client.post("/api/v1/channels", json={
        "name": "Football Test", "slug": "football-test", "niche": "Football",
        "default_engine": "football",
    }).json()
    project = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Lance manual",
        "topic": "Fonte sintética; nenhum gol ou placar inferido", "format": "horizontal",
    }).json()
    url = f"/api/v1/projects/{project['id']}/football"
    body = {
        "expected_revision": 0, "aspect": "horizontal",
        "shots": [
            {"asset_id": asset_id, "in_ms": 0, "out_ms": 1500,
             "role": "build_up", "focus_x": 0.5, "focus_y": 0.5},
            {"asset_id": asset_id, "in_ms": 1500, "out_ms": 3000,
             "role": "action", "verified_event_id": "human-event-1"},
            {"asset_id": asset_id, "in_ms": 1500, "out_ms": 3000,
             "role": "replay", "verified_event_id": "human-event-1"},
        ],
        "score_label": None, "score_source_url": None,
    }
    bad = {**body, "shots": [{**body["shots"][1], "verified_event_id": None}]}
    assert client.put(url, json=bad).status_code == 422
    wrong_replay = {**body, "shots": [body["shots"][2], body["shots"][1]]}
    assert client.put(url, json=wrong_replay).status_code == 422
    unsourced_score = {**body, "score_label": "Equipe A 1 × 0 Equipe B"}
    assert client.put(url, json=unsourced_score).status_code == 422
    saved = client.put(url, json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["status"] == "REVIEW_REQUIRED"
    assert saved.json()["shots"][0]["source_sha256"] == sha256_file(source)
    assert client.post(f"{url}/render").status_code == 409
    assert client.post(f"{url}/approve", json={
        "expected_revision": 1, "events_verified": False,
        "rights_confirmed": True, "score_verified": False,
    }).status_code == 422
    approved = client.post(f"{url}/approve", json={
        "expected_revision": 1, "events_verified": True,
        "rights_confirmed": True, "score_verified": False,
    })
    assert approved.status_code == 200, approved.text
    queued = client.post(f"{url}/render")
    assert queued.status_code == 202, queued.text
    assert client.post(f"{url}/render").json()["job_id"] == queued.json()["job_id"]
    assert media_one()
    job = client.get(f"/api/v1/jobs/{queued.json()['job_id']}").json()
    assert job["status"] == "SUCCEEDED", job["error"]
    assert job["result"]["replay_count"] == 1
    assert job["result"]["shots"] == 3
    assert 4400 <= job["result"]["duration_ms"] <= 4800
    download = f"{url}/render/{job['id']}"
    assert client.get(download).status_code == 200
    assert client.post(f"{url}/render").json()["job_id"] == queued.json()["job_id"]
    body["expected_revision"] = 1
    body["shots"][1]["out_ms"] = 2800
    assert client.put(url, json=body).status_code == 200
    assert client.put(url, json=body).status_code == 409
    assert client.get(download).status_code == 409
