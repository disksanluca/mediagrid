import pytest
from fastapi.testclient import TestClient

from apps.api.engines import ENGINES, get_engine


def test_required_pilot_engines_are_registered() -> None:
    assert set(ENGINES) == {"football", "geo", "music", "clips", "politics", "trends"}
    assert all(len(engine.visual_types) >= 4 for engine in ENGINES.values())
    assert all(len(engine.review_checks) >= 2 for engine in ENGINES.values())


def test_unknown_engine_is_explicit_error() -> None:
    with pytest.raises(ValueError, match="Unknown engine"):
        get_engine("unknown")


@pytest.mark.parametrize("engine_id", sorted(ENGINES))
def test_engine_plan_and_reordered_edl_keep_review_contract(
    client: TestClient, engine_id: str
) -> None:
    channel = client.post(
        "/api/v1/channels",
        json={
            "name": engine_id.title(),
            "slug": engine_id,
            "niche": engine_id,
            "default_engine": engine_id,
        },
    )
    assert channel.status_code == 201
    project = client.post(
        "/api/v1/projects",
        json={
            "channel_id": channel.json()["id"],
            "title": "Pauta local",
            "topic": "Assunto a verificar",
            "format": "vertical",
        },
    )
    assert project.status_code == 201
    project_id = project.json()["id"]
    plan = client.post(f"/api/v1/projects/{project_id}/plan")
    assert plan.status_code == 200
    body = plan.json()
    assert body["engine"] == engine_id
    assert body["review_checks"] == list(ENGINES[engine_id].review_checks)
    reordered = list(reversed(body["scenes"]))
    updated = client.put(
        f"/api/v1/projects/{project_id}/plan",
        json={"scenes": reordered, "hook": body["hook"], "angle": body["angle"]},
    )
    assert updated.status_code == 200
    saved = updated.json()
    assert saved["plan"]["review_checks"] == body["review_checks"]
    assert [scene["scene_id"] for scene in saved["edl"]["tracks"]["video"]] == [
        scene["id"] for scene in reordered
    ]
