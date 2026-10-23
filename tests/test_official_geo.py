import hashlib

import httpx
from fastapi.testclient import TestClient

from apps.api import official_geo
from apps.api.config import get_settings
from apps.api.database import SessionLocal
from apps.api.models import Project, ProjectStatus
from apps.api.routes.projects import legacy_hash
from workers.render.main import source_label


def municipality(identifier: int, name: str, state: str) -> dict:
    return {
        "municipio-id": identifier,
        "municipio-nome": name,
        "UF-sigla": state,
        "UF-nome": "São Paulo" if state == "SP" else "Rio de Janeiro",
        "regiao-nome": "Sudeste",
        "regiao-imediata-nome": name,
        "regiao-intermediaria-nome": name,
    }


def ibge_response(request: httpx.Request) -> httpx.Response:
    assert request.url.params["view"] == "nivelado"
    if request.url.path.endswith("/municipios"):
        return httpx.Response(
            200,
            json=[
                municipality(3550308, "São Paulo", "SP"),
                municipality(3304557, "Rio de Janeiro", "RJ"),
            ],
        )
    if request.url.path.endswith("/municipios/3550308"):
        return httpx.Response(200, json=municipality(3550308, "São Paulo", "SP"))
    return httpx.Response(404)


def test_ibge_search_import_and_edit_preserve_source(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        official_geo,
        "ibge_client",
        lambda: httpx.Client(transport=httpx.MockTransport(ibge_response)),
    )
    channel = client.post(
        "/api/v1/channels",
        json={
            "name": "Mundo em Mapas",
            "slug": "mundo-em-mapas",
            "niche": "Geografia",
            "default_engine": "geo",
        },
    ).json()
    search = client.get("/api/v1/geo/municipalities", params={"query": "sao paulo"})
    assert search.status_code == 200
    assert [row["id"] for row in search.json()] == [3550308]
    assert search.json()[0]["source_url"].endswith("/3550308?view=nivelado")

    imported = client.post(
        "/api/v1/geo/projects",
        json={"channel_id": channel["id"], "municipality_id": 3550308},
    )
    assert imported.status_code == 201
    project = imported.json()
    assert project["plan"]["origin"] == "OFFICIAL_SOURCE"
    assert project["plan"]["engine"] == "geo"
    assert project["content_type"] == "knowledge"
    assert len(project["plan"]["scenes"]) == 3
    assert len(project["plan"]["source_refs"][0]["snapshot_sha256"]) == 64
    claims = client.get(f"/api/v1/projects/{project['id']}/claims").json()
    assert len(claims) == 3
    assert {claim["scene_id"] for claim in claims} == {
        scene["id"] for scene in project["plan"]["scenes"]
    }
    assert all(claim["status"] == "REVIEW_REQUIRED" for claim in claims)
    assert all(claim["published_at"] is None for claim in claims)
    assert all(claim["source_checked_at"].endswith("+00:00") for claim in claims)
    assert any("regiao-nome: Sudeste" in claim["support_excerpt"] for claim in claims)
    assert "Sudeste" in project["plan"]["scenes"][-1]["narration"]
    assert project["script"]["segments"] == [
        scene["narration"] for scene in project["plan"]["scenes"]
    ]
    assert len(project["edl"]["tracks"]["video"]) == 3
    assert source_label(project["plan"]) == "Fonte: IBGE"

    plan = project["plan"]
    plan["scenes"][0]["narration"] += " Revisado."
    updated = client.put(
        f"/api/v1/projects/{project['id']}/plan",
        json={"scenes": plan["scenes"], "hook": plan["hook"], "angle": plan["angle"]},
    )
    assert updated.status_code == 200
    assert updated.json()["plan"]["origin"] == "MANUAL"
    assert updated.json()["plan"]["source_refs"] == plan["source_refs"]
    assert source_label(updated.json()["plan"]) == "Fonte: IBGE"
    assert all(claim["status"] == "REVIEW_REQUIRED" for claim in
               client.get(f"/api/v1/projects/{project['id']}/claims").json())


def test_ibge_wrong_channel_and_unavailable_source(client: TestClient, monkeypatch) -> None:
    channel = client.post(
        "/api/v1/channels",
        json={"name": "Música", "slug": "musica", "niche": "Música", "default_engine": "music"},
    ).json()
    assert client.post(
        "/api/v1/geo/projects",
        json={"channel_id": channel["id"], "municipality_id": 3550308},
    ).status_code == 422
    assert client.get("/api/v1/geo/municipalities", params={"query": "   "}).status_code == 422

    def offline():
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(official_geo, "ibge_client", offline)
    assert client.get("/api/v1/geo/municipalities", params={"query": "Sao"}).status_code == 503
    assert client.get("/api/v1/projects").json() == []


def test_geo_import_claims_block_review_until_human_approval(
    client: TestClient, monkeypatch, tmp_path, seed_completed_render,
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    monkeypatch.setattr(
        official_geo, "ibge_client",
        lambda: httpx.Client(transport=httpx.MockTransport(ibge_response)),
    )
    channel = client.post("/api/v1/channels", json={
        "name": "Geo evidência", "slug": "geo-evidencia", "niche": "Geografia",
        "default_engine": "geo",
    }).json()
    project = client.post("/api/v1/geo/projects", json={
        "channel_id": channel["id"], "municipality_id": 3550308,
    }).json()
    project_id = project["id"]
    claims = client.get(f"/api/v1/projects/{project_id}/claims").json()
    assert len(claims) == 3
    seed_completed_render(project_id, b"synthetic-geo-video")
    base = f"/api/v1/projects/{project_id}"
    review = {
        "source_urls": [claims[0]["source_url"]],
        "facts_confirmed": True, "rights_confirmed": True,
        "notes": "Conferido com a API do IBGE", "caption": "Revisão de teste",
    }
    assert client.post(f"{base}/review", json=review).status_code == 409
    assert client.get(f"{base}/export").status_code == 409
    for claim in claims:
        approved = client.post(f"{base}/claims/{claim['id']}/approve", json={
            "expected_revision": claim["revision"], "source_opened": True,
            "excerpt_matches": True, "context_checked": True,
        })
        assert approved.status_code == 200, approved.text
    assert client.post(f"{base}/review", json=review).status_code == 200
    assert client.get(f"{base}/export").status_code == 200
    changed = client.put(f"{base}/claims/{claims[0]['id']}", json={
        "scene_id": claims[0]["scene_id"], "text": claims[0]["text"],
        "source_url": claims[0]["source_url"], "source_title": claims[0]["source_title"],
        "published_at": None,
        "support_excerpt": claims[0]["support_excerpt"] + "; conferido novamente",
        "expected_revision": 1,
    })
    assert changed.status_code == 200, changed.text
    assert changed.json()["source_checked_at"] is None
    assert client.get(f"{base}/export").status_code == 409
    removed = client.post(f"{base}/claims/{claims[0]['id']}/remove", json={
        "expected_revision": 2,
    })
    assert removed.status_code == 200, removed.text
    assert client.post(f"{base}/review", json=review).status_code == 409


def test_preexisting_approved_geo_export_keeps_its_review(
    client: TestClient, monkeypatch, tmp_path, seed_completed_render,
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    channel = client.post("/api/v1/channels", json={
        "name": "Geo legado", "slug": "geo-legado", "niche": "Geografia",
        "default_engine": "geo",
    }).json()
    project = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Geo antes do gate",
        "topic": "Revisão existente", "content_type": "video",
    }).json()
    project_id = project["id"]
    client.post(f"/api/v1/projects/{project_id}/plan")
    seed_completed_render(project_id, b"synthetic-preexisting-geo")
    base = f"/api/v1/projects/{project_id}"
    review = {"source_urls": ["https://example.org/old-geo-source"], "facts_confirmed": True,
              "rights_confirmed": True, "notes": "Novo gate requer claims",
              "caption": "Teste"}
    assert client.post(f"{base}/review", json=review).status_code == 409
    with SessionLocal() as db:
        stored = db.get(Project, project_id)
        assert stored is not None
        stored.plan = {**stored.plan, "review": {
            "video_sha256": hashlib.sha256(b"synthetic-preexisting-geo").hexdigest(),
            "edl_sha256": legacy_hash(stored.edl),
            "source_urls": ["https://example.org/old-geo-source"],
            "facts_confirmed": True, "rights_confirmed": True,
        }}
        stored.status = ProjectStatus.APPROVED.value
        db.commit()
    assert client.get(f"{base}/export").status_code == 200
