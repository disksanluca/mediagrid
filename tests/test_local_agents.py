"""Creative AI uses the existing local queue and never auto-approves drafts."""

import json

import httpx
import pytest

from apps.api.config import get_settings
from apps.api.creative.contracts import CreativeBrief, CreativeStoryboard, StoryboardShot
from apps.api.creative.local_agents import (
    AgentDirections,
    ReferenceNotes,
    ScriptDraft,
    loopback_url,
    motion_compatibility,
)
from apps.api.database import SessionLocal
from apps.api.models import Job
from apps.api.motion_contracts.registry import load_recipe
from workers.render.main import media_one


def foundation(client, monkeypatch, tmp_path):
    settings = get_settings()
    monkeypatch.setattr(settings, "mediagrid_agents_enabled", True)
    monkeypatch.setattr(settings, "mediagrid_agents_model", "qwen3:4b-instruct")
    monkeypatch.setattr(settings, "ollama_base_url", "http://127.0.0.1:11434")
    monkeypatch.setattr(settings, "mediagrid_data_dir", tmp_path)
    channel = client.post("/api/v1/channels", json={
        "name": "POV local", "slug": "pov-local", "niche": "Fiction",
        "default_engine": "clips",
    }).json()
    project = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Fictional resale",
        "topic": "A fictional first sale", "format": "vertical",
    }).json()
    dna = client.put(f"/api/v1/channels/{channel['id']}/creative-dna", json={
        "expected_revision": 0,
        "content": {"palette": ["#121A20", "#D2DFE8"],
                    "font_display": "Space Grotesk", "font_body": "Space Grotesk",
                    "tone": "Fictional and intimate"},
    })
    assert dna.status_code == 200, dna.text
    root = f"/api/v1/projects/{project['id']}/creative"
    brief = client.put(root + "/brief", json={
        "expected_revision": 0,
        "content": {"topic": "A fictional first phone resale", "audience": "Young adults",
                    "objective": "Tell an original second-person fictional story",
                    "duration_ms": 45000, "factual_mode": "FICTIONAL"},
    })
    assert brief.status_code == 200, brief.text
    return project, root


def script_response():
    locations = ["room", "bus", "cafe", "room", "repair", "cafe"]
    stages = ["setup", "inspection", "purchase", "discovery", "evidence", "lesson"]
    return {"schema_version": "local_script_v1", "title": "Your first sale",
            "pov_second_person": True, "fictional": True, "character_id": "person-1",
            "character_description": "A cautious young adult with a blue jacket",
            "beats": [{"id": f"beat-{i}",
                       "narration": (
                           f"Você observa a cena fictícia {i} com bastante cuidado e atenção."
                       ),
                       "visual": f"A mesa e o telefone aparecem na cena {i}.",
                       "location_id": locations[i-1], "character_id": "person-1",
                       "character_action": f"Examina o aparelho no passo {i}.",
                       "prop_state": [f"telefone no estado {i}"],
                       "narration_target_ms": 5000,
                       "arc_stage": stages[i-1]}
                      for i in range(1, 7)], "claims_to_verify": []}


def mock_ollama(monkeypatch, content):
    observed = []
    def handler(request):
        observed.append(request)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3:4b-instruct",
                                                        "digest": "a" * 64}]})
        if request.url.path == "/api/ps":
            return httpx.Response(200, json={"models": []})
        body = json.loads(request.content)
        assert request.url.path == "/api/chat"
        assert body["stream"] is True and "tools" not in body
        assert body["format"]["type"] == "object"
        return httpx.Response(200, json={"model": "qwen3:4b-instruct", "done": True,
                                         "message": {"content": json.dumps(content)},
                                         "prompt_eval_count": 180, "eval_count": 310})
    original = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(
        transport=httpx.MockTransport(handler), **kwargs,
    ))
    return observed


def test_local_agent_job_persists_validated_draft(client, monkeypatch, tmp_path):
    project, root = foundation(client, monkeypatch, tmp_path)
    observed = mock_ollama(monkeypatch, script_response())
    queued = client.post(root + "/agents/jobs", json={
        "task": "script", "expected_brief_revision": 1,
        "expected_dna_revision": 1,
    })
    assert queued.status_code == 202, queued.text
    assert client.post(root + "/agents/jobs", json={"task": "script",
        "expected_brief_revision": 1, "expected_dna_revision": 1}).status_code == 429
    assert media_one()
    with SessionLocal() as db:
        job = db.get(Job, queued.json()["id"])
        assert job.status == "SUCCEEDED"
        assert ScriptDraft.model_validate(job.result["content"]).beats[0].character_id == "person-1"
        assert job.result["provider"] == "ollama_loopback"
        assert job.result["review_status"] == "NEEDS_REVIEW"
        assert len(observed) == 3
        assert db.get(Job, job.id).project_id == project["id"]
    assert len(client.get(root + "/agents/jobs").json()) == 1


def test_invalid_json_fails_without_fake_success(client, monkeypatch, tmp_path):
    _, root = foundation(client, monkeypatch, tmp_path)
    mock_ollama(monkeypatch, {"schema_version": "local_script_v1", "beats": []})
    queued = client.post(root + "/agents/jobs", json={
        "task": "script", "expected_brief_revision": 1,
        "expected_dna_revision": 1,
    }).json()
    assert media_one()
    with SessionLocal() as db:
        job = db.get(Job, queued["id"])
        assert job.status == "FAILED" and job.result is None


def test_offline_and_unsafe_origin_fail_closed(client, monkeypatch, tmp_path):
    _, root = foundation(client, monkeypatch, tmp_path)
    monkeypatch.setattr(get_settings(), "ollama_base_url", "http://192.168.1.10:11434")
    with pytest.raises(ValueError):
        loopback_url()
    assert client.post(root + "/agents/jobs", json={"task": "script",
        "expected_brief_revision": 1, "expected_dna_revision": 1}).status_code == 503
    monkeypatch.setattr(get_settings(), "mediagrid_agents_enabled", False)
    assert client.get("/api/v1/creative/agents/status").json()["state"] == "DISABLED"


def test_storyboard_requires_human_direction_choice(client, monkeypatch, tmp_path):
    _, root = foundation(client, monkeypatch, tmp_path)
    response = client.post(root + "/agents/jobs", json={
        "task": "storyboard", "expected_brief_revision": 1,
        "expected_dna_revision": 1,
    })
    assert response.status_code == 409


def test_factual_script_requires_reviewed_source(client, monkeypatch, tmp_path):
    _, root = foundation(client, monkeypatch, tmp_path)
    revised = client.put(root + "/brief", json={
        "expected_revision": 1,
        "content": {"topic": "An election result", "audience": "Adults",
                    "objective": "Explain a verified election result",
                    "duration_ms": 45000, "factual_mode": "FACT_CHECK_REQUIRED"},
    })
    assert revised.status_code == 200, revised.text
    response = client.post(root + "/agents/jobs", json={
        "task": "script", "expected_brief_revision": 2,
        "expected_dna_revision": 1,
    })
    assert response.status_code == 409
    assert "source" in response.text.lower()


def test_script_rejects_wrong_pov(client, monkeypatch, tmp_path):
    _, root = foundation(client, monkeypatch, tmp_path)
    draft = script_response()
    draft["pov_second_person"] = False
    mock_ollama(monkeypatch, draft)
    queued = client.post(root + "/agents/jobs", json={
        "task": "script", "expected_brief_revision": 1,
        "expected_dna_revision": 1,
    }).json()
    assert media_one()
    with SessionLocal() as db:
        job = db.get(Job, queued["id"])
        assert job.status == "FAILED" and job.result is None


def test_fictional_script_rejects_unfounded_percentage():
    draft = script_response()
    draft["beats"][5]["narration"] = (
        "Você pede um desconto de 30% ao vendedor e conclui a negociação fictícia."
    )
    with pytest.raises(ValueError, match="30%"):
        ScriptDraft.model_validate(draft)


def test_motion_suggestion_cannot_claim_six_shot_storyboard_ready():
    brief = CreativeBrief(topic="A fictional sale", audience="Adults",
                          objective="Tell a six beat POV narrative", format="vertical",
                          duration_ms=45000, factual_mode="FICTIONAL")
    shots = [StoryboardShot(id=f"shot-{index}", start_ms=index*7500,
                            duration_ms=7500, beat=f"Original beat {index}",
                            visual_description="An original visual scene")
             for index in range(6)]
    board = CreativeStoryboard(direction_id="direction-1", duration_ms=45000,
                               shots=shots)
    recipe = load_recipe("geo.route-explainer", "1.2.0")
    state, reasons = motion_compatibility(brief, board, recipe)
    assert state == "BLOCKED_RECIPE_MISMATCH"
    assert any("scene count" in reason for reason in reasons)


def test_agent_rejects_truncated_palette_colors():
    direction = {
        "title": "Original motion", "thesis": "An original six-shot visual journey",
        "rationale": "Show a coherent original vector narrative.",
        "emotional_arc": "Curiosity to resolution", "rhythm": "hybrid",
        "typography": "IBM Plex Sans", "composition": "Layered vector panels",
        "motion_language": "Controlled camera drift", "palette": ["#101A26", "#F2E"],
        "estimated_complexity": "LOW",
    }
    with pytest.raises(ValueError, match="six-digit"):
        AgentDirections.model_validate({"directions": [
            {**direction, "id": f"direction-{index}"} for index in range(3)
        ]})
    with pytest.raises(ValueError, match="six-digit"):
        ReferenceNotes.model_validate({
            "composition": "Layered editorial cards", "typography": "IBM Plex Sans",
            "palette": ["#101A26", "#F2E7D"], "motion": "Controlled camera drift",
            "provenance_warning": "No external sources were inspected.",
        })
