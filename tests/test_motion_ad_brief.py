"""Motion ads are real editable projects assembled from creator supplied copy."""

from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.config import get_settings


def _channel(client: TestClient) -> str:
    response = client.post("/api/v1/channels", json={
        "name": "Estúdio", "slug": "estudio-motion", "niche": "Produtos",
        "default_engine": "clips",
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _brief(channel_id: str, format: str = "vertical") -> dict:
    return {
        "channel_id": channel_id, "format": format,
        "product_name": "Produto fictício", "audience": "criadores independentes",
        "hook": "Organize suas ideias em um só lugar.",
        "problem": "Arquivos dispersos tornam o trabalho mais lento.",
        "benefit": "Reúna seus rascunhos em uma área de trabalho.",
        "call_to_action": "Conheça o produto fictício.",
        "brand_color": "#c4d4ef",
    }


def _cards(timeline: dict) -> dict:
    return {
        item["id"]: item
        for track in timeline["edl"]["tracks"]
        for item in track["items"]
        if item["id"].startswith("ad-card-")
    }


def test_brief_creates_editable_ad_and_animation_without_invented_copy(
    client: TestClient,
) -> None:
    brief = _brief(_channel(client))
    response = client.post("/api/v1/motion-ads/projects", json=brief)
    assert response.status_code == 201, response.text
    project = response.json()
    assert project["content_type"] == "motion_ad"
    assert project["status"] == "SCRIPTED"
    assert project["plan"]["origin"] == "BRIEF_BASED"
    assert project["plan"]["initial_motion_ad_brief"] == brief
    assert len(project["plan"]["initial_motion_ad_brief_sha256"]) == 64
    assert [scene["narration"] for scene in project["plan"]["scenes"]] == [
        brief[key] for key in ("hook", "problem", "benefit", "call_to_action")
    ]
    timeline = client.get(f"/api/v1/projects/{project['id']}/edl-v2").json()
    assert timeline["revision"] == 1
    assert timeline["renderer"] == "timeline-v2"
    cards = _cards(timeline)
    assert set(cards) == {"ad-card-benefit", "ad-card-cta"}
    assert cards["ad-card-benefit"]["preset"] == "motion_card_v1"
    assert cards["ad-card-benefit"]["params"]["body"] == brief["benefit"]
    assert cards["ad-card-cta"]["params"]["text"] == brief["call_to_action"]
    assert cards["ad-card-benefit"]["start_ms"] == sum(
        round(scene["duration_seconds"] * 1000)
        for scene in project["plan"]["scenes"][:2]
    )
    preview = client.get(f"/api/v1/projects/{project['id']}/preview")
    assert preview.status_code == 200, preview.text
    overlays = preview.json()["props"]["overlays"]
    assert {item["preset"] for item in overlays} == {"motion_card_v1"}
    assert {item["body"] for item in overlays} == {
        brief["benefit"], brief["product_name"]
    }
    queued = client.post(f"/api/v1/projects/{project['id']}/render")
    assert queued.status_code == 202, queued.text
    job = client.get(f"/api/v1/jobs/{queued.json()['job_id']}").json()
    assert job["status"] in {"QUEUED", "WAITING_FOR_WORKER"}


def test_brief_validation_and_generic_overwrite_are_blocked(client: TestClient) -> None:
    channel_id = _channel(client)
    brief = _brief(channel_id)
    for changed in (
        {"hook": "  "}, {"problem": brief["hook"]},
        {"problem": brief["hook"].upper()},
        {"product_name": " A "},
        {"brand_color": "blue"}, {"format": "carousel"},
    ):
        assert client.post("/api/v1/motion-ads/projects", json={
            **brief, **changed,
        }).status_code == 422
    assert client.post("/api/v1/projects", json={
        "channel_id": channel_id, "title": "Bypass", "topic": "Some copy",
        "content_type": "motion_ad",
    }).status_code == 422
    project_id = client.post("/api/v1/motion-ads/projects", json=brief).json()["id"]
    assert client.post(f"/api/v1/projects/{project_id}/plan").status_code == 409


def test_scene_edit_keeps_brief_and_moves_cards(client: TestClient) -> None:
    brief = _brief(_channel(client))
    project = client.post("/api/v1/motion-ads/projects", json=brief).json()
    project_id = project["id"]
    before = client.get(f"/api/v1/projects/{project_id}/edl-v2").json()
    scenes = project["plan"]["scenes"]
    scenes[0]["duration_seconds"] += 2
    scenes[2]["duration_seconds"] += 1
    scenes[2]["narration"] = "Uma proposta revisada pelo criador."
    scenes[3]["on_screen_text"] = "Veja mais agora."
    payload = {
        "scenes": scenes, "hook": project["plan"]["hook"],
        "angle": project["plan"]["angle"],
        "expected_revision": before["revision"],
        "expected_legacy_sha256": before["legacy_sha256"],
    }
    response = client.put(f"/api/v1/projects/{project_id}/plan", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["plan"]["initial_motion_ad_brief"] == brief
    after = client.get(f"/api/v1/projects/{project_id}/edl-v2").json()
    assert after["revision"] == 2
    cards = _cards(after)
    assert cards["ad-card-benefit"]["start_ms"] == sum(
        round(scene["duration_seconds"] * 1000) for scene in scenes[:2]
    )
    assert cards["ad-card-benefit"]["duration_ms"] == round(
        scenes[2]["duration_seconds"] * 1000
    )
    assert cards["ad-card-benefit"]["params"]["body"] == scenes[2]["narration"]
    assert cards["ad-card-cta"]["params"]["text"] == scenes[3]["on_screen_text"]
    assert client.put(f"/api/v1/projects/{project_id}/plan", json=payload).status_code == 409
    assert client.put(f"/api/v1/projects/{project_id}/plan", json={
        **payload, "expected_revision": 2, "expected_legacy_sha256": after["legacy_sha256"],
        "scenes": scenes[:-1],
    }).status_code == 422


def test_card_edit_keeps_original_brief(client: TestClient) -> None:
    brief = _brief(_channel(client))
    project_id = client.post("/api/v1/motion-ads/projects", json=brief).json()["id"]
    timeline = client.get(f"/api/v1/projects/{project_id}/edl-v2").json()
    card = next(item for track in timeline["edl"]["tracks"]
                for item in track["items"] if item["id"] == "ad-card-benefit")
    card["params"]["color"] = "#abcdef"
    response = client.put(f"/api/v1/projects/{project_id}/edl-v2", json={
        "expected_revision": timeline["revision"],
        "expected_legacy_sha256": timeline["legacy_sha256"],
        "edl": timeline["edl"],
    })
    assert response.status_code == 200, response.text
    current = client.get(f"/api/v1/projects/{project_id}").json()
    assert current["plan"]["initial_motion_ad_brief"] == brief
    preview = client.get(f"/api/v1/projects/{project_id}/preview").json()
    assert "#abcdef" in {item["color"] for item in preview["props"]["overlays"]}


def test_unverified_ad_cannot_be_approved_or_exported(
    client: TestClient, monkeypatch, tmp_path: Path, seed_completed_render,
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    project_id = client.post("/api/v1/motion-ads/projects", json={
        **_brief(_channel(client)), "format": "horizontal",
    }).json()["id"]
    assert client.get(f"/api/v1/projects/{project_id}/export").status_code == 409
    seed_completed_render(project_id, b"synthetic-unapproved-ad")
    review = {
        "source_urls": ["https://example.org/evidence"],
        "facts_confirmed": True, "rights_confirmed": True,
        "notes": "Revisão técnica sem prova factual.", "caption": "Teste sintético",
    }
    response = client.post(f"/api/v1/projects/{project_id}/review", json=review)
    assert response.status_code == 409, response.text
    assert client.get(f"/api/v1/projects/{project_id}/export").status_code == 409
