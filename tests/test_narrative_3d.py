"""3D stories keep revisions, worker state and blocking approval honest."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.config import get_settings
from apps.api.ingestion import sha256_file
from workers.render.main import media_one


def create_story(client: TestClient) -> tuple[str, str, dict]:
    channel = client.post("/api/v1/channels", json={
        "name": "Narrativa Original", "slug": "narrativa-original", "niche": "3D",
        "default_engine": "music",
    }).json()
    project = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Migo e a luz",
        "topic": "Uma pequena história visual original em três tomadas.",
        "content_type": "narrative_3d", "format": "horizontal",
    }).json()
    url = f"/api/v1/projects/{project['id']}/narrative-3d"
    body = {
        "expected_revision": 0, "title": "Migo e a luz", "aspect": "horizontal",
        "shots": [
            {"duration_ms": 1500, "beat_text": "Migo vê uma luz no atelier.",
             "action": "notice", "camera": "wide", "lighting": "calm"},
            {"duration_ms": 1500, "beat_text": "Ele se aproxima com cuidado.",
             "action": "reach", "camera": "medium", "lighting": "tense"},
            {"duration_ms": 1500, "beat_text": "A luz reage ao seu toque.",
             "action": "react", "camera": "close", "lighting": "bright"},
        ], "audio_asset_id": None,
    }
    return project["id"], url, body


def test_3d_story_validates_and_waits_for_missing_worker(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("apps.api.routes.narrative_3d.blender_executable", lambda: None)
    _, url, body = create_story(client)
    assert client.put(url, json={**body, "shots": body["shots"][:2]}).status_code == 422
    duplicates = [*body["shots"]]
    duplicates[1] = {**duplicates[1], "beat_text": duplicates[0]["beat_text"]}
    assert client.put(url, json={**body, "shots": duplicates}).status_code == 422
    saved = client.put(url, json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 1
    assert saved.json()["rig_version"] == "migo_3d_v1"
    assert client.put(url, json=body).status_code == 409
    waiting = client.post(f"{url}/blocking")
    assert waiting.status_code == 202, waiting.text
    assert waiting.json()["status"] == "WAITING_FOR_WORKER"
    assert client.post(f"{url}/blocking").json()["job_id"] == waiting.json()["job_id"]
    assert client.post(f"{url}/final").status_code == 409
    assert client.post(f"{url}/approve-blocking", json={
        "expected_revision": 1, "watched_full_preview": True,
        "character_continuity_checked": True, "story_timing_checked": True,
    }).status_code == 409
    assert client.get(f"{url}/blocking/render/{waiting.json()['job_id']}").status_code == 409
    revised = {**body, "expected_revision": 1, "title": "Migo encontra a luz"}
    assert client.put(url, json=revised).json()["revision"] == 2
    assert client.get(f"{url}/blocking/render-status").json() is None


def test_3d_blender_blocking_and_final_are_real(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = os.getenv("MEDIAGRID_TEST_BLENDER")
    if not executable or not Path(executable).is_file():
        pytest.skip("Official Blender 4.5 LTS portable runtime not configured in CI")
    monkeypatch.setattr(get_settings(), "mediagrid_blender_path", Path(executable))
    _, url, body = create_story(client)
    sequence = client.put(url, json=body).json()
    queued = client.post(f"{url}/blocking").json()
    assert queued["status"] == "QUEUED"
    assert media_one()
    blocking = client.get(f"/api/v1/jobs/{queued['job_id']}").json()
    assert blocking["status"] == "SUCCEEDED", blocking["error"]
    assert blocking["result"]["shots"] == 3
    assert blocking["result"]["frames"] == 54
    assert blocking["result"]["audio_kind"] == "silence"
    assert blocking["result"]["sha256"] == sha256_file(Path(blocking["result"]["output"]))
    assert client.get(f"{url}/blocking/render/{queued['job_id']}").status_code == 200
    approved = client.post(f"{url}/approve-blocking", json={
        "expected_revision": sequence["revision"], "watched_full_preview": True,
        "character_continuity_checked": True, "story_timing_checked": True,
    })
    assert approved.status_code == 200, approved.text
    assert approved.json()["blocking_sha256"] == blocking["result"]["sha256"]
    final_job = client.post(f"{url}/final").json()
    assert media_one()
    final = client.get(f"/api/v1/jobs/{final_job['job_id']}").json()
    assert final["status"] == "SUCCEEDED", final["error"]
    assert final["result"]["frames"] == 108
    assert 4200 <= final["result"]["duration_ms"] <= 4800
    assert client.get(f"{url}/final/render/{final_job['job_id']}").status_code == 200
    revised = {**body, "expected_revision": 1, "title": "Migo mudou o roteiro"}
    assert client.put(url, json=revised).status_code == 200
    assert client.get(f"{url}/final/render/{final_job['job_id']}").status_code == 409
