"""A queued render cannot silently publish a later revision as its own result."""

from copy import deepcopy

from fastapi.testclient import TestClient

from apps.api.database import SessionLocal
from apps.api.models import Job, Project
from workers.render.main import render_one


def test_render_rejects_timeline_changed_after_queue(client: TestClient) -> None:
    channel = client.post("/api/v1/channels", json={
        "name": "Canal local", "slug": "canal-local", "niche": "clips",
        "default_engine": "clips",
    }).json()
    project = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Prova de snapshot",
        "topic": "Primeira fala real.\nSegunda fala real.\nTerceira fala real.",
    }).json()
    project_id = project["id"]
    plan = client.post(f"/api/v1/projects/{project_id}/plan").json()
    for index, scene in enumerate(plan["scenes"]):
        scene["narration"] = f"Narração concreta da cena {index + 1}, revisada antes da fila."
    assert client.put(f"/api/v1/projects/{project_id}/plan", json={
        "scenes": plan["scenes"], "hook": plan["hook"], "angle": plan["angle"],
    }).status_code == 200
    queued = client.post(f"/api/v1/projects/{project_id}/render")
    assert queued.status_code == 202
    job_id = queued.json()["job_id"]

    with SessionLocal() as db:
        stored = db.get(Project, project_id)
        assert stored and stored.edl
        changed = deepcopy(stored.edl)
        changed["tracks"]["captions"][0]["text"] = "Texto atualizado depois da fila"
        stored.edl = changed
        db.commit()

    assert render_one() is True
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        assert job and job.status == "FAILED"
        assert "changed after" in (job.error or "")
        assert job.result is None
