"""Server topology must fail closed until its prerequisites are configured."""

import pytest
from fastapi.testclient import TestClient

from apps.api.config import Settings, get_settings
from apps.api.database import SessionLocal
from apps.api.main import validate_runtime_config
from apps.api.models import Job
from workers.render.main import main as local_worker_main
from workers.render.narrative_3d import blender_executable


def server_settings(**overrides) -> Settings:
    values = {
        "mediagrid_mode": "SERVER",
        "mediagrid_server_experimental": True,
        "database_url": "postgresql+psycopg://user:secret@localhost/mediagrid",
        "mediagrid_admin_password": "private-admin-password",
        "mediagrid_session_secret": "private-session-secret",
        "mediagrid_public_url": "https://mediagrid.example",
        "allow_paid_ai": False,
        "dry_run": True,
    }
    values.update(overrides)
    return Settings(**values)


def test_server_configuration_fails_closed() -> None:
    validate_runtime_config(server_settings())
    for values, message in [
        ({"database_url": "sqlite:///./data/mediagrid.db"}, "PostgreSQL"),
        ({"mediagrid_public_url": "http://mediagrid.example"}, "HTTPS"),
        ({"mediagrid_admin_password": None}, "ADMIN_PASSWORD"),
        ({"allow_paid_ai": True}, "ALLOW_PAID_AI"),
        ({"dry_run": False}, "DRY_RUN"),
        ({"mediagrid_server_experimental": False}, "experimental"),
    ]:
        with pytest.raises(RuntimeError, match=message):
            validate_runtime_config(server_settings(**values))
    validate_runtime_config(Settings(mediagrid_mode="LOCAL"))


def test_local_worker_refuses_server_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_mode", "SERVER")
    with pytest.raises(RuntimeError, match="cannot process server jobs"):
        local_worker_main(["--once"])
    assert blender_executable() is None


def test_server_jobs_wait_without_desktop_worker(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = client.post("/api/v1/channels", json={
        "name": "Canal Web", "slug": "canal-web", "niche": "Conhecimento",
        "default_engine": "geo",
    }).json()
    project = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Pauta com fatos",
        "topic": "\n".join([
            "O primeiro trecho traz uma premissa editorial a conferir.",
            "O segundo trecho depende de uma fonte antes da publicação.",
            "O terceiro trecho será revisado pela pessoa responsável.",
        ]),
    }).json()
    plan = client.post(f"/api/v1/projects/{project['id']}/plan")
    assert plan.status_code == 200
    monkeypatch.setattr(get_settings(), "mediagrid_mode", "SERVER")
    monkeypatch.setattr("apps.api.main.auth.is_authenticated", lambda _: True)
    queued = client.post(f"/api/v1/projects/{project['id']}/voice")
    assert queued.status_code == 202, queued.text
    assert queued.json()["status"] == "WAITING_FOR_WORKER"
    assert client.post(f"/api/v1/projects/{project['id']}/voice").status_code == 409
    with SessionLocal() as db:
        job = db.get(Job, queued.json()["job_id"])
        assert job is not None
        job.status = "FAILED"
        db.commit()
    retried = client.post(f"/api/v1/jobs/{queued.json()['job_id']}/retry")
    assert retried.status_code == 200
    assert retried.json()["status"] == "WAITING_FOR_WORKER"
