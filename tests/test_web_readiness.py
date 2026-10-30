"""Server topology must fail closed until its prerequisites are configured."""

from collections import defaultdict

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


def test_local_companion_requires_https_and_credentials() -> None:
    values = {
        "mediagrid_mode": "LOCAL",
        "mediagrid_public_url": "https://studio.example.ts.net",
        "mediagrid_admin_password": "private-admin-password",
        "mediagrid_session_secret": "private-session-secret-at-least-32-chars",
    }
    validate_runtime_config(Settings(**values))
    for url in (
        "http://studio.example.ts.net",
        "https://public.example",
        "https://studio.example.ts.net/other",
        "https://user@studio.example.ts.net",
        "https://studio.example.ts.net?unsafe=1",
        "https://studio.example.ts.net:bad",
    ):
        with pytest.raises(RuntimeError, match="HTTPS origin"):
            validate_runtime_config(Settings(**{**values, "mediagrid_public_url": url}))
    for missing in ("mediagrid_admin_password", "mediagrid_session_secret"):
        with pytest.raises(RuntimeError, match="companion requires"):
            validate_runtime_config(Settings(**{**values, missing: None}))
    with pytest.raises(RuntimeError, match="16-character password"):
        validate_runtime_config(Settings(**{**values, "mediagrid_admin_password": "short"}))


def test_local_companion_login_origin_and_cookie(
    monkeypatch: pytest.MonkeyPatch, client: TestClient,
) -> None:
    origin = "https://studio.example.ts.net"
    monkeypatch.setenv("MEDIAGRID_MODE", "LOCAL")
    monkeypatch.setenv("MEDIAGRID_PUBLIC_URL", origin)
    monkeypatch.setenv("MEDIAGRID_ADMIN_PASSWORD", "private-admin-password")
    monkeypatch.setenv("MEDIAGRID_SESSION_SECRET", "private-session-secret-at-least-32-chars")
    get_settings.cache_clear()
    try:
        assert client.get("/api/v1/auth/session").json() == {
            "authenticated": False, "login_required": True,
        }
        assert client.get("/api/v1/projects").status_code == 401
        assert client.post("/api/v1/auth/login", json={"password": "private-admin-password"},
                           headers={"origin": "https://foreign.example"}).status_code == 403
        response = client.post(
            "/api/v1/auth/login", json={"password": "private-admin-password"},
            headers={"origin": origin},
        )
        assert response.status_code == 200
        assert "secure" in response.headers["set-cookie"].lower()
        cookie = response.headers["set-cookie"].split(";", 1)[0]
        assert client.get("/api/v1/projects", headers={"cookie": cookie}).status_code == 200
        payload = {
            "name": "Canal privado", "slug": "canal-privado", "niche": "Ficcao",
            "default_engine": "football",
        }
        path = "/api/v1/channels"
        assert client.post(path, json=payload, headers={"cookie": cookie}).status_code == 403
        assert client.post(path, json=payload, headers={
            "cookie": cookie, "origin": "https://foreign.example",
        }).status_code == 403
        assert client.post(path, json=payload, headers={
            "cookie": cookie, "origin": origin,
        }).status_code == 201
    finally:
        get_settings.cache_clear()


def test_companion_login_cannot_bypass_limit_with_forwarded_header(
    monkeypatch: pytest.MonkeyPatch, client: TestClient,
) -> None:
    monkeypatch.setenv("MEDIAGRID_MODE", "LOCAL")
    monkeypatch.setenv("MEDIAGRID_PUBLIC_URL", "https://studio.example.ts.net")
    monkeypatch.setenv("MEDIAGRID_ADMIN_PASSWORD", "private-admin-password")
    monkeypatch.setenv("MEDIAGRID_SESSION_SECRET", "private-session-secret-at-least-32-chars")
    monkeypatch.setattr("apps.api.auth._failed_attempts", defaultdict(list))
    get_settings.cache_clear()
    try:
        for index in range(10):
            response = client.post(
                "/api/v1/auth/login", json={"password": "wrong"},
                headers={"origin": "https://studio.example.ts.net",
                         "x-forwarded-for": f"192.0.2.{index + 1}"},
            )
            assert response.status_code == 401
        response = client.post(
            "/api/v1/auth/login", json={"password": "private-admin-password"},
            headers={"origin": "https://studio.example.ts.net",
                     "x-forwarded-for": "198.51.100.1"},
        )
        assert response.status_code == 429
    finally:
        get_settings.cache_clear()


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
