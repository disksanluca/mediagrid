"""Scheduled MusicBrainz drafts remain local, idempotent and review gated."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from apps.api import official_music
from apps.api.database import SessionLocal
from apps.api.models import MusicDraftSchedule
from apps.api.routes import music as music_routes
from workers.render import scheduled_music

RELEASE_ID = "b29e94e7-0b0b-3a66-ab06-e02f8fa5054f"
RELEASE = {
    "id": RELEASE_ID, "title": "Clube da Esquina",
    "artist-credit": [
        {"name": "Milton Nascimento", "joinphrase": " & "},
        {"name": "Lô Borges"},
    ],
    "first-release-date": "1972", "primary-type": "Album",
}


def _setup(client: TestClient, monkeypatch, provider_status: int = 200) -> tuple[str, dict]:
    monkeypatch.setattr(official_music, "_last_request", 0.0)
    monkeypatch.setattr(official_music, "musicbrainz_client", lambda: httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(
            provider_status, json=RELEASE if provider_status == 200 else {},
        )),
    ))
    channel = client.post("/api/v1/channels", json={
        "name": "Música", "slug": "musica-agendada", "niche": "Música",
        "default_engine": "music",
    }).json()
    payload = {
        "channel_id": channel["id"], "release_group_id": RELEASE_ID,
        "scheduled_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    return channel["id"], payload


def _due(schedule_id: str) -> None:
    with SessionLocal() as db:
        item = db.get(MusicDraftSchedule, schedule_id)
        assert item is not None
        item.run_after = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
        db.commit()


def test_scheduled_draft_is_idempotent_and_worker_creates_review_gated_project(
    client: TestClient, monkeypatch,
) -> None:
    _, payload = _setup(client, monkeypatch)
    path = "/api/v1/music/drafts/schedules"
    first = client.post(path, json=payload)
    assert first.status_code == 201, first.text
    schedule = first.json()
    assert schedule["status"] == "PENDING"
    assert client.post(path, json=payload).json()["id"] == schedule["id"]
    assert len(client.get(path).json()) == 1
    assert scheduled_music.draft_one() is False
    _due(schedule["id"])
    assert scheduled_music.draft_one() is True
    finished = client.get(path).json()[0]
    assert finished["status"] == "SUCCEEDED"
    assert finished["attempt"] == 1
    assert finished["project_id"]
    assert scheduled_music.draft_one() is False
    projects = client.get("/api/v1/projects").json()
    assert len(projects) == 1
    assert projects[0]["id"] == finished["project_id"]
    assert projects[0]["plan"]["source_refs"][0]["snapshot_sha256"]
    claims = client.get(f"/api/v1/projects/{finished['project_id']}/claims").json()
    assert len(claims) == 3
    assert {claim["status"] for claim in claims} == {"REVIEW_REQUIRED"}
    assert client.get(f"/api/v1/projects/{finished['project_id']}/export").status_code == 409


def test_scheduled_draft_failure_retry_and_cancel_during_fetch(
    client: TestClient, monkeypatch,
) -> None:
    _, payload = _setup(client, monkeypatch, provider_status=503)
    path = "/api/v1/music/drafts/schedules"
    created = client.post(path, json=payload).json()
    _due(created["id"])
    assert scheduled_music.draft_one() is True
    failed = client.get(path).json()[0]
    assert failed["status"] == "FAILED" and failed["attempt"] == 1
    assert failed["project_id"] is None
    assert client.post(f"{path}/{created['id']}/retry").json()["status"] == "PENDING"

    def cancel_during_fetch(identifier):
        assert str(identifier) == RELEASE_ID
        assert client.post(f"{path}/{created['id']}/cancel").json()["status"] == "CANCELLED"
        return official_music._release_group(RELEASE), datetime.now(UTC)

    monkeypatch.setattr(scheduled_music, "fetch_release_group", cancel_during_fetch)
    assert scheduled_music.draft_one() is True
    assert client.get(path).json()[0]["status"] == "CANCELLED"
    assert client.get("/api/v1/projects").json() == []
    assert scheduled_music.draft_one() is False


def test_schedule_rejects_wrong_time_channel_and_server_mode(
    client: TestClient, monkeypatch,
) -> None:
    channel_id, payload = _setup(client, monkeypatch)
    path = "/api/v1/music/drafts/schedules"
    invalid_time = {**payload, "scheduled_at": datetime.now(UTC).isoformat()}
    assert client.post(path, json=invalid_time).status_code == 422
    naive_time = {**payload, "scheduled_at": "2026-10-24T12:00:00"}
    assert client.post(path, json=naive_time).status_code == 422
    wrong = client.post("/api/v1/channels", json={
        "name": "Geo", "slug": "geo-agendado", "niche": "Geo", "default_engine": "geo",
    }).json()
    assert client.post(path, json={**payload, "channel_id": wrong["id"]}).status_code == 422
    assert client.post(path, json={**payload, "channel_id": channel_id}).status_code == 201
    monkeypatch.setattr(scheduled_music.get_settings(), "mediagrid_mode", "SERVER")
    assert scheduled_music.draft_one() is False
    with SessionLocal() as db, pytest.raises(HTTPException) as error:
        music_routes.schedule_release_group(
            music_routes.ScheduleReleaseGroup.model_validate(payload), db,
        )
    assert error.value.status_code == 503
