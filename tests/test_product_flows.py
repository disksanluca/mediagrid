from fastapi.testclient import TestClient

from apps.api.config import get_settings
from apps.api.database import SessionLocal
from apps.api.models import Job, Project
from workers.render.main import recover_interrupted_jobs


def test_plan_can_be_edited_and_render_only_queued_once(client: TestClient) -> None:
    channel = client.post(
        "/api/v1/channels",
        json={
            "name": "Pulso Musical",
            "slug": "pulso-musical",
            "niche": "Música",
            "default_engine": "music",
        },
    ).json()
    created = client.post(
        "/api/v1/projects",
        json={
            "channel_id": channel["id"],
            "title": "História do disco",
            "topic": "História de um disco brasileiro",
            "format": "vertical",
        },
    )
    assert created.status_code == 201
    project_id = created.json()["id"]
    plan = client.post(f"/api/v1/projects/{project_id}/plan").json()
    plan["scenes"][0]["on_screen_text"] = "Nova abertura"
    updated = client.put(
        f"/api/v1/projects/{project_id}/plan",
        json={"hook": "Abertura revisada", "angle": plan["angle"], "scenes": plan["scenes"]},
    )
    assert updated.status_code == 200
    assert updated.json()["plan"]["scenes"][0]["on_screen_text"] == "Nova abertura"
    assert updated.json()["edl"]["tracks"]["captions"][0]["text"] == "Nova abertura"
    assert client.post(f"/api/v1/projects/{project_id}/render").status_code == 202
    assert client.post(f"/api/v1/projects/{project_id}/render").status_code == 409
    assert client.get(f"/api/v1/projects/{project_id}/output").status_code == 404


def test_public_mode_requires_login_and_cookie(monkeypatch, client: TestClient) -> None:
    monkeypatch.setenv("MEDIAGRID_MODE", "CLOUD")
    monkeypatch.setenv("MEDIAGRID_ADMIN_PASSWORD", "test-password-only")
    monkeypatch.setenv("MEDIAGRID_SESSION_SECRET", "test-signing-secret-only")
    monkeypatch.setenv("MEDIAGRID_PUBLIC_URL", "https://mediagrid.example")
    get_settings.cache_clear()
    try:
        assert client.get("/api/v1/system/health").status_code == 200
        assert client.get("/api/v1/projects").status_code == 401
        assert client.post("/api/v1/auth/login", json={"password": "wrong"}).status_code == 401
        response = client.post("/api/v1/auth/login", json={"password": "test-password-only"})
        assert response.status_code == 200
        assert "httponly" in response.headers["set-cookie"].lower()
        assert "secure" in response.headers["set-cookie"].lower()
        cookie_header = response.headers["set-cookie"].split(";", 1)[0]
        assert client.get("/api/v1/projects", headers={"cookie": cookie_header}).status_code == 200
        assert (
            client.post(
                "/api/v1/channels",
                json={},
                headers={"origin": "https://other.example", "cookie": cookie_header},
            ).status_code
            == 403
        )
        assert (
            client.post("/api/v1/auth/logout", headers={"cookie": cookie_header}).status_code == 200
        )
        assert client.get("/api/v1/projects").status_code == 401
    finally:
        get_settings.cache_clear()


def test_interrupted_render_is_recovered(client: TestClient) -> None:
    channel = client.post(
        "/api/v1/channels",
        json={"name": "Canal", "slug": "canal", "niche": "Geo", "default_engine": "geo"},
    ).json()
    project = client.post(
        "/api/v1/projects",
        json={"channel_id": channel["id"], "title": "Mapa", "topic": "Mapa do mundo"},
    ).json()
    client.post(f"/api/v1/projects/{project['id']}/plan")
    queued = client.post(f"/api/v1/projects/{project['id']}/render").json()
    with SessionLocal() as db:
        job = db.get(Job, queued["job_id"])
        project_record = db.get(Project, project["id"])
        assert job and project_record
        job.status = "RUNNING"
        job.attempt = 1
        project_record.status = "RENDERING"
        db.commit()
    recover_interrupted_jobs()
    assert client.get(f"/api/v1/jobs/{queued['job_id']}").json()["status"] == "QUEUED"
    assert client.get(f"/api/v1/projects/{project['id']}").json()["status"] == "SCRIPTED"
