"""Factual explainers require per-claim citations and human review before export."""

import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.config import get_settings
from apps.api.database import SessionLocal
from apps.api.models import Project


def test_manual_politics_requires_claims_even_for_legacy_video(
    client: TestClient, monkeypatch, tmp_path: Path, seed_completed_render,
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    channel = client.post("/api/v1/channels", json={
        "name": "Política local", "slug": "politica-local", "niche": "Política",
        "default_engine": "politics",
    }).json()
    response = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Rascunho político",
        "topic": "Tema ainda sem fontes", "content_type": "video",
    })
    assert response.status_code == 201, response.text
    project_id = response.json()["id"]
    assert response.json()["content_type"] == "knowledge"
    client.post(f"/api/v1/projects/{project_id}/plan")
    seed_completed_render(project_id, b"synthetic-politics-video")
    review = {
        "source_urls": ["https://example.org/registro"],
        "facts_confirmed": True, "rights_confirmed": True,
        "notes": "Revisão de teste", "caption": "Teste sintético",
    }
    assert client.post(f"/api/v1/projects/{project_id}/review", json=review).status_code == 409
    with SessionLocal() as db:
        stored = db.get(Project, project_id)
        assert stored is not None
        stored.content_type = "video"  # A preexisting political draft must obey the same gate.
        db.commit()
    assert client.post(f"/api/v1/projects/{project_id}/review", json=review).status_code == 409


def test_claim_ledger_blocks_uncited_or_changed_knowledge_export(
    client: TestClient, monkeypatch, tmp_path: Path, seed_completed_render,
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    channel = client.post("/api/v1/channels", json={
        "name": "Pesquisa", "slug": "knowledge-test", "niche": "Geografia",
        "default_engine": "geo",
    }).json()
    project = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Explainer com fontes",
        "topic": "Teste do registro de fontes", "format": "vertical",
    }).json()
    project_id = project["id"]
    plan = client.post(f"/api/v1/projects/{project_id}/plan").json()
    base = f"/api/v1/projects/{project_id}"
    claim_body = {
        "scene_id": plan["scenes"][0]["id"],
        "text": "A fonte oficial descreve o dado usado nesta cena.",
        "source_url": "https://example.org/documento",
        "source_title": "Documento oficial de teste",
        "published_at": "2025-05-01",
        "support_excerpt": "Trecho verificável de teste que sustenta a alegação.",
    }
    assert client.post(f"{base}/claims", json={
        **claim_body, "scene_id": "missing",
    }).status_code == 422
    assert client.post(f"{base}/claims", json={
        **claim_body, "published_at": "2999-01-01",
    }).status_code == 422
    added = client.post(f"{base}/claims", json=claim_body)
    assert added.status_code == 201, added.text
    claim = added.json()
    assert claim["status"] == "REVIEW_REQUIRED"
    assert client.get(base).json()["content_type"] == "knowledge"
    claim_url = f"{base}/claims/{claim['id']}"
    assert client.post(f"{claim_url}/approve", json={
        "expected_revision": 1, "source_opened": False,
        "excerpt_matches": True, "context_checked": True,
    }).status_code == 422

    seed_completed_render(project_id, b"synthetic-knowledge-video")
    review = {
        "source_urls": [claim_body["source_url"]],
        "facts_confirmed": True, "rights_confirmed": True,
        "notes": "Fonte, data e cena conferidas",
        "caption": "Vídeo sintético para teste de evidências.",
    }
    assert client.post(f"{base}/review", json=review).status_code == 409
    approved_claim = client.post(f"{claim_url}/approve", json={
        "expected_revision": 1, "source_opened": True,
        "excerpt_matches": True, "context_checked": True,
    })
    assert approved_claim.status_code == 200, approved_claim.text
    assert approved_claim.json()["status"] == "APPROVED"
    missing_source = {**review, "source_urls": ["https://example.org/outro"]}
    assert client.post(f"{base}/review", json=missing_source).status_code == 409
    assert client.post(f"{base}/review", json=review).status_code == 200
    package = client.get(f"{base}/export")
    assert package.status_code == 200, package.text
    with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["knowledge_claims"][0]["id"] == claim["id"]
    assert len(manifest["approved_review"]["claim_digest"]) == 64
    revised_body = {**claim_body, "expected_revision": 1,
                    "support_excerpt": "Trecho corrigido pela pessoa revisora após reler a fonte."}
    revised = client.put(claim_url, json=revised_body)
    assert revised.status_code == 200, revised.text
    assert revised.json()["status"] == "REVIEW_REQUIRED"
    assert client.get(base).json()["status"] == "QC"
    assert client.get(f"{base}/export").status_code == 409
    assert client.put(claim_url, json=revised_body).status_code == 409
    removed = client.post(f"{claim_url}/remove", json={
        "expected_revision": 2,
    })
    assert removed.status_code == 200
    assert client.get(f"{base}/claims").json() == []
    assert client.post(f"{base}/review", json=review).status_code == 409

    new_claim = client.post(f"{base}/claims", json=claim_body).json()
    assert client.post(f"{base}/claims/{new_claim['id']}/approve", json={
        "expected_revision": 1, "source_opened": True,
        "excerpt_matches": True, "context_checked": True,
    }).status_code == 200
    updated_scenes = [dict(scene) for scene in plan["scenes"]]
    updated_scenes[0]["narration"] = "Narração factual alterada após revisar as fontes."
    changed_plan = client.put(f"{base}/plan", json={
        "scenes": updated_scenes, "hook": plan["hook"], "angle": plan["angle"],
    })
    assert changed_plan.status_code == 200, changed_plan.text
    stale_claim = client.get(f"{base}/claims").json()[0]
    assert stale_claim["status"] == "REVIEW_REQUIRED"
    assert stale_claim["reviewed_at"] is None
    assert stale_claim["revision"] == 2
