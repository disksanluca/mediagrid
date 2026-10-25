"""Creative foundation REST behavior, persistence, review gates and concurrency."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from alembic import command
from fastapi.testclient import TestClient

from apps.api.database import SessionLocal
from apps.api.main import app
from apps.api.migrate import _config
from apps.api.models import Asset, CreativeDNARevision, KnowledgeClaim, Project

DNA = {
    "palette": ["#101827", "#E6EEF4"], "font_display": "Arial Black",
    "font_body": "Arial", "tone": "Investigativo", "energy": "balanced",
    "must_have": ["Fontes visíveis"], "avoid": ["Afirmações sem evidência"],
}
BRIEF = {
    "topic": "Como uma proposta legislativa será analisada",
    "audience": "Público brasileiro", "objective": "Explicar o processo sem concluir o mérito",
    "format": "vertical", "duration_ms": 12000, "fps": 30,
    "factual_mode": "FICTIONAL", "sources": [], "asset_ids": [],
}
BOARD = {
    "direction_id": "evidence-led", "duration_ms": 12000, "fps": 30,
    "shots": [
        {"id": "opening", "start_ms": 0, "duration_ms": 6000,
         "beat": "Abrir pergunta", "on_screen_text": "O que vem agora?",
         "visual_description": "Tipografia em fundo contrastante",
         "motion_intent": "Revelação gradual"},
        {"id": "closing", "start_ms": 6000, "duration_ms": 6000,
         "beat": "Fechar contexto", "on_screen_text": "Leia as fontes",
         "visual_description": "Quadro de referência legível",
         "motion_intent": "Pausa e dissolvência"},
    ],
}


def _seed(client: TestClient) -> tuple[str, str]:
    channel = client.post("/api/v1/channels", json={
        "name": "Política", "slug": "politica-criativa", "niche": "Política",
        "default_engine": "politics",
    })
    assert channel.status_code == 201, channel.text
    channel_id = channel.json()["id"]
    project = client.post("/api/v1/projects", json={
        "channel_id": channel_id, "title": "Projeto criativo", "topic": BRIEF["topic"],
    })
    assert project.status_code == 201, project.text
    return channel_id, project.json()["id"]


def _foundation(client: TestClient, channel_id: str, project_id: str,
                brief: dict | None = None) -> tuple[str, str]:
    dna_path = f"/api/v1/channels/{channel_id}/creative-dna"
    root = f"/api/v1/projects/{project_id}/creative"
    dna = client.put(dna_path, json={"expected_revision": 0, "content": DNA})
    assert dna.status_code == 200, dna.text
    saved = client.put(f"{root}/brief", json={
        "expected_revision": 0, "content": brief or BRIEF,
    })
    assert saved.status_code == 200, saved.text
    generated = client.post(f"{root}/directions", json={
        "expected_revision": 0, "expected_brief_revision": 1,
        "expected_dna_revision": 1,
    })
    assert generated.status_code == 200, generated.text
    directions = generated.json()
    assert directions["origin"] == "deterministic_reference"
    assert len(directions["content"]["directions"]) == 3
    assert len({item["id"] for item in directions["content"]["directions"]}) == 3
    repeated = client.post(f"{root}/directions", json={
        "expected_revision": 1, "expected_brief_revision": 1,
        "expected_dna_revision": 1,
    })
    assert repeated.status_code == 200 and repeated.json()["id"] == directions["id"]
    return dna_path, root


def _storyboard(client: TestClient, root: str, board: dict | None = None,
                expected_revision: int = 0, direction_revision: int = 1) -> dict:
    response = client.put(f"{root}/storyboard", json={
        "expected_revision": expected_revision,
        "expected_direction_revision": direction_revision,
        "content": board or BOARD,
    })
    assert response.status_code == 200, response.text
    return response.json()


def _decide(client: TestClient, root: str, review: dict, board_revision: int = 1,
            review_revision: int = 0, decision: str = "APPROVE"):
    return client.post(f"{root}/decision", json={
        "expected_revision": review_revision,
        "expected_storyboard_revision": board_revision,
        "expected_snapshot_sha256": review["current_snapshot_sha256"],
        "decision": decision, "actor": "Criador local",
        "storyboard_reviewed": True, "rights_checked": True, "facts_checked": True,
    })


def test_creative_persists_and_mutation_invalidates_approval(client: TestClient) -> None:
    channel_id, project_id = _seed(client)
    dna_path, root = _foundation(client, channel_id, project_id)
    first = _storyboard(client, root)
    assert first["revision"] == 1 and first["status"] == "CURRENT"
    review = client.get(f"{root}/review").json()
    approved = _decide(client, root, review)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED_STORYBOARD"
    with TestClient(app) as restarted:
        assert restarted.get(dna_path).json()["revision"] == 1
        assert restarted.get(f"{root}/brief").json()["sha256"]
        assert restarted.get(f"{root}/directions").json()["revision"] == 1
        assert restarted.get(f"{root}/storyboard").json()["content"] == first["content"]
        assert restarted.get(f"{root}/review").json()["status"] == "APPROVED_STORYBOARD"
        with SessionLocal() as db:
            assert db.get(Project, project_id).edl is None
        changed = {**BOARD, "shots": [
            {**BOARD["shots"][0], "on_screen_text": "Outra pergunta?"}, BOARD["shots"][1],
        ]}
        assert _storyboard(restarted, root, changed, expected_revision=1)["revision"] == 2
        stale = restarted.get(f"{root}/review").json()
        assert stale["status"] == "STALE"
        assert stale["review"]["storyboard_revision"] == 1
        assert _decide(restarted, root, stale, board_revision=1,
                       review_revision=1).status_code == 409
        fresh = _decide(restarted, root, stale, board_revision=2, review_revision=1)
        assert fresh.status_code == 200, fresh.text
        assert fresh.json()["status"] == "APPROVED_STORYBOARD"
        with SessionLocal() as db:
            project = db.get(Project, project_id)
            project.plan = {"source_refs": [], "origin": "MANUAL"}
            db.commit()
        assert restarted.get(f"{root}/review").json()["status"] == "STALE"
        updated_dna = restarted.put(dna_path, json={
            "expected_revision": 1, "content": {**DNA, "tone": "Didático"},
        })
        assert updated_dna.status_code == 200
        assert restarted.get(f"{root}/directions").json()["status"] == "STALE"
        assert restarted.get(f"{root}/review").json()["status"] == "STALE"


def test_revision_conflicts_and_strict_timing(client: TestClient) -> None:
    channel_id, project_id = _seed(client)
    dna_path, root = _foundation(client, channel_id, project_id)
    assert client.put(dna_path, json={"expected_revision": 0, "content": DNA}).status_code == 409
    assert client.put(f"{root}/brief", json={
        "expected_revision": 0, "content": BRIEF,
    }).status_code == 409
    assert client.post(f"{root}/directions", json={
        "expected_revision": 0, "expected_brief_revision": 1,
        "expected_dna_revision": 1,
    }).status_code == 409
    gap = {**BOARD, "shots": [BOARD["shots"][0], {
        **BOARD["shots"][1], "start_ms": 6100,
    }]}
    assert client.put(f"{root}/storyboard", json={
        "expected_revision": 0, "expected_direction_revision": 1,
        "content": gap,
    }).status_code == 422
    _storyboard(client, root)
    assert client.put(f"{root}/storyboard", json={
        "expected_revision": 0, "expected_direction_revision": 1,
        "content": BOARD,
    }).status_code == 409
    review = client.get(f"{root}/review").json()
    assert _decide(client, root, review).status_code == 200
    assert _decide(client, root, review).status_code == 409
    invalid = client.put(f"{root}/brief", json={
        "expected_revision": 1, "content": {**BRIEF, "untrusted": "data"},
    })
    assert invalid.status_code == 422
    long_brief = {**BRIEF, "topic": "T" * 500, "audience": "P" * 240,
                  "objective": "O" * 600}
    assert client.put(f"{root}/brief", json={
        "expected_revision": 1, "content": long_brief,
    }).status_code == 200
    assert client.post(f"{root}/directions", json={
        "expected_revision": 1, "expected_brief_revision": 2,
        "expected_dna_revision": 1,
    }).status_code == 200


def test_real_parallel_writes_use_one_revision(client: TestClient) -> None:
    channel_id, _ = _seed(client)
    path = f"/api/v1/channels/{channel_id}/creative-dna"
    gate = Barrier(2)

    def write(tone: str) -> int:
        gate.wait(timeout=5)
        return client.put(path, json={
            "expected_revision": 0, "content": {**DNA, "tone": tone},
        }).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(write, ("Tom A", "Tom B")))
    assert statuses == [200, 409]
    assert client.get(path).json()["revision"] == 1


def test_rights_and_facts_gate_review(client: TestClient) -> None:
    channel_id, project_id = _seed(client)
    with SessionLocal() as db:
        asset = Asset(name="Arquivo", media_type="image/png", path="isolated",
                      sha256="a" * 64, rights_status="UNKNOWN", commercial_use=False)
        claim = KnowledgeClaim(
            project_id=project_id, scene_id="opening", text="Afirmação de teste",
            source_url="https://example.org/source", source_title="Fonte de teste",
            support_excerpt="Trecho de teste com contexto suficiente",
        )
        db.add_all([asset, claim])
        db.commit()
        asset_id, claim_id = asset.id, claim.id
    factual_brief = {**BRIEF, "factual_mode": "FACT_CHECK_REQUIRED",
                     "asset_ids": [asset_id], "sources": [{
                         "url": "https://example.org/source", "title": "Fonte de teste",
                         "fact_reviewed": False,
                     }]}
    _, root = _foundation(client, channel_id, project_id, factual_brief)
    board = {**BOARD, "shots": [{**BOARD["shots"][0],
                                 "asset_ids": [asset_id], "claim_ids": [claim_id]},
                                BOARD["shots"][1]]}
    _storyboard(client, root, board)
    review = client.get(f"{root}/review").json()
    assert any("RIGHTS_BLOCKED" in reason for reason in review["blockers"])
    assert _decide(client, root, review).status_code == 409
    with SessionLocal() as db:
        asset = db.get(Asset, asset_id)
        claim = db.get(KnowledgeClaim, claim_id)
        asset.rights_status = "OWNED"
        asset.commercial_use = True
        claim.status = "APPROVED"
        db.commit()
    review = client.get(f"{root}/review").json()
    assert any("reviewed sources" in reason for reason in review["blockers"])
    assert _decide(client, root, review).status_code == 409
    corrected = {**factual_brief, "sources": [{
        "url": "https://example.org/source", "title": "Fonte de teste",
        "fact_reviewed": True,
    }]}
    assert client.put(f"{root}/brief", json={
        "expected_revision": 1, "content": corrected,
    }).status_code == 200
    assert client.get(f"{root}/directions").json()["status"] == "STALE"
    assert client.post(f"{root}/directions", json={
        "expected_revision": 1, "expected_brief_revision": 2,
        "expected_dna_revision": 1,
    }).status_code == 200
    _storyboard(client, root, board, expected_revision=1, direction_revision=2)
    review = client.get(f"{root}/review").json()
    approved = _decide(client, root, review, board_revision=2)
    assert approved.status_code == 200, approved.text
    with SessionLocal() as db:
        claim = db.get(KnowledgeClaim, claim_id)
        claim.status = "REVIEW_REQUIRED"
        claim.revision += 1
        db.commit()
    assert client.get(f"{root}/review").json()["status"] == "STALE"


def test_downgrade_refuses_persisted_creative_data(client: TestClient) -> None:
    channel_id, project_id = _seed(client)
    _foundation(client, channel_id, project_id)
    with pytest.raises(RuntimeError, match="contains creative revisions"):
        command.downgrade(_config(), "0011_music_draft_schedule")
    with SessionLocal() as db:
        assert db.query(CreativeDNARevision).count() == 1
    assert client.get(f"/api/v1/channels/{channel_id}/creative-dna").status_code == 200


def test_project_format_change_blocks_old_storyboard(client: TestClient) -> None:
    channel_id, project_id = _seed(client)
    _, root = _foundation(client, channel_id, project_id)
    _storyboard(client, root)
    review = client.get(f"{root}/review").json()
    assert _decide(client, root, review).json()["status"] == "APPROVED_STORYBOARD"
    with SessionLocal() as db:
        db.get(Project, project_id).format = "horizontal"
        db.commit()
    changed = client.get(f"{root}/review").json()
    assert changed["status"] == "STALE"
    assert any("format differs" in reason for reason in changed["blockers"])
