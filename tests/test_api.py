from fastapi.testclient import TestClient


def create_channel(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/channels",
        json={
            "name": "Mundo em Mapas",
            "slug": "mundo-em-mapas",
            "niche": "Geografia",
            "default_engine": "geo",
            "brand_profile": {"accent": "#57d7e8"},
            "editorial_profile": {"tone": "claro"},
        },
    )
    assert response.status_code == 201
    return response.json()


def test_health_and_zero_cost_defaults(client: TestClient) -> None:
    assert client.get("/api/v1/system/health").json() == {"status": "ok"}
    system = client.get("/api/v1/system").json()
    assert system["mode"] == "LOCAL"
    assert system["paid_ai_allowed"] is False
    assert system["dry_run"] is True
    assert system["ffmpeg"] is True


def test_channel_slug_is_unique(client: TestClient) -> None:
    create_channel(client)
    duplicate = client.post(
        "/api/v1/channels",
        json={
            "name": "Outro nome",
            "slug": "mundo-em-mapas",
            "niche": "Geografia",
            "default_engine": "geo",
        },
    )
    assert duplicate.status_code == 409


def test_project_generates_validated_plan_and_edl(client: TestClient) -> None:
    channel = create_channel(client)
    project_response = client.post(
        "/api/v1/projects",
        json={
            "channel_id": channel["id"],
            "title": "A fronteira mais curiosa do mundo",
            "topic": "A fronteira entre Baarle-Nassau e Baarle-Hertog",
            "format": "vertical",
        },
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    plan_response = client.post(f"/api/v1/projects/{project_id}/plan")
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["engine"] == "geo"
    assert len(plan["scenes"]) == 5
    assert plan["target_duration_seconds"] == 45

    project = client.get(f"/api/v1/projects/{project_id}").json()
    assert project["status"] == "SCRIPTED"
    assert len(project["edl"]["tracks"]["video"]) == 5

    render = client.post(f"/api/v1/projects/{project_id}/render")
    assert render.status_code == 202
    jobs = client.get("/api/v1/jobs").json()
    assert jobs[0]["job_type"] == "RENDER"
    assert jobs[0]["status"] == "QUEUED"
