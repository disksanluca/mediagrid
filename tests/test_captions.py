"""Timed captions remain reviewable and bound to the original media hash."""

from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.config import get_settings
from apps.api.routes import transcripts
from tests.test_ingestion import synthetic_mp4
from workers.render.main import media_one


def test_manual_words_cues_review_and_sidecars(client: TestClient, tmp_path: Path) -> None:
    video = synthetic_mp4(tmp_path / "spoken.mp4")
    asset = client.post("/api/v1/assets", files={
        "file": ("spoken.mp4", video, "video/mp4"),
    }, data={"rights_status": "OWNED"}).json()
    asset_id = asset["id"]
    url = f"/api/v1/assets/{asset_id}/transcript-v2"
    assert client.get(url).status_code == 404
    assert client.get(f"/api/v1/assets/{asset_id}/captions.srt").status_code == 409
    body = {
        "expected_revision": 0, "language": "pt",
        "words": [
            {"start_ms": 100, "end_ms": 500, "text": "Olá"},
            {"start_ms": 550, "end_ms": 1000, "text": "mundo."},
        ],
        "cues": [{"start_ms": 100, "end_ms": 1000, "text": "Olá mundo."}],
    }
    saved = client.put(url, json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 1
    assert saved.json()["status"] == "REVIEW_REQUIRED"
    assert len(saved.json()["words"]) == 2
    assert client.put(url, json=body).status_code == 409
    assert client.get(f"/api/v1/assets/{asset_id}/captions.srt").status_code == 409
    approved = client.post(f"/api/v1/assets/{asset_id}/captions/approve", json={
        "expected_revision": 1,
    })
    assert approved.status_code == 200
    assert approved.json()["revision"] == 2
    srt = client.get(f"/api/v1/assets/{asset_id}/captions.srt")
    assert srt.status_code == 200
    assert "00:00:00,100 --> 00:00:01,000\nOlá mundo." in srt.text
    vtt = client.get(f"/api/v1/assets/{asset_id}/captions.vtt")
    assert vtt.text.startswith("WEBVTT\n\n00:00:00.100 --> 00:00:01.000")
    render_url = f"/api/v1/assets/{asset_id}/captions/render"
    queued = client.post(render_url, json={"expected_revision": 2})
    assert queued.status_code == 202, queued.text
    assert client.get(f"{render_url}/{queued.json()['job_id']}").status_code == 409
    assert media_one()
    job = client.get(f"/api/v1/jobs/{queued.json()['job_id']}").json()
    assert job["status"] == "SUCCEEDED", job["error"]
    assert client.post(render_url, json={"expected_revision": 2}).json()["job_id"] == job["id"]
    captioned = client.get(f"{render_url}/{job['id']}")
    assert captioned.status_code == 200 and captioned.content
    body["expected_revision"] = 2
    body["words"][0]["text"] = "Oi"
    body["cues"][0]["text"] = "Oi mundo."
    edited = client.put(url, json=body)
    assert edited.status_code == 200
    assert edited.json()["status"] == "REVIEW_REQUIRED"
    assert client.get(f"/api/v1/assets/{asset_id}/captions.srt").status_code == 409
    assert client.get(f"{render_url}/{job['id']}").status_code == 409
    body["expected_revision"] = 3
    body["cues"].append({"start_ms": 900, "end_ms": 1500, "text": "Sobreposta"})
    assert client.put(url, json=body).status_code == 422
    body["cues"].pop()
    source = get_settings().mediagrid_data_dir / "assets" / asset_id
    source.write_bytes(b"tampered")
    assert client.post(f"/api/v1/assets/{asset_id}/captions/approve", json={
        "expected_revision": 3,
    }).status_code == 409


def test_word_asr_explicitly_unavailable_without_model(
    client: TestClient, tmp_path: Path
) -> None:
    video = synthetic_mp4(tmp_path / "without-model.mp4")
    asset = client.post("/api/v1/assets", files={
        "file": ("without-model.mp4", video, "video/mp4"),
    }).json()
    assert client.get("/api/v1/assets/asr-status").json()["word_asr_available"] is False
    response = client.post(f"/api/v1/assets/{asset['id']}/transcribe-words")
    assert response.status_code == 503
    assert not client.get("/api/v1/jobs").json()


def test_manual_save_waits_for_queued_asr(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    video = synthetic_mp4(tmp_path / "queued.mp4")
    asset = client.post("/api/v1/assets", files={
        "file": ("queued.mp4", video, "video/mp4"),
    }).json()
    monkeypatch.setattr(transcripts, "available", lambda: True)
    queued = client.post(f"/api/v1/assets/{asset['id']}/transcribe-words")
    assert queued.status_code == 202
    response = client.put(f"/api/v1/assets/{asset['id']}/transcript-v2", json={
        "expected_revision": 0, "language": "pt", "words": [],
        "cues": [{"start_ms": 0, "end_ms": 500, "text": "Manual"}],
    })
    assert response.status_code == 409
