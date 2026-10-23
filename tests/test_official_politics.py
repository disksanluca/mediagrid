import io
import json
import zipfile

import httpx
from fastapi.testclient import TestClient

from apps.api import official_politics
from apps.api.config import get_settings
from apps.api.database import SessionLocal
from apps.api.models import Project, ProjectStatus
from workers.render.main import source_label


def official_response(request: httpx.Request) -> httpx.Response:
    proposal = {
        "id": 123456,
        "siglaTipo": "PL",
        "numero": 42,
        "ano": 2026,
        "ementa": "Institui diretrizes para publicar dados públicos em formato acessível.",
        "dataApresentacao": "2026-10-16T11:28",
        "statusProposicao": {
            "dataHora": "2026-10-16T11:28",
            "descricaoTramitacao": "Apresentação de Proposição",
        },
    }
    if request.url.path.endswith("/proposicoes"):
        assert request.url.params["siglaTipo"] == "PL"
        assert request.url.params["ano"] == "2026"
        return httpx.Response(200, json={"dados": [proposal]})
    assert request.url.path.endswith("/proposicoes/123456")
    return httpx.Response(200, json={"dados": proposal})


def test_official_politics_creates_editable_sourced_plan(
    client: TestClient, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    monkeypatch.setattr(
        official_politics,
        "official_client",
        lambda: httpx.Client(transport=httpx.MockTransport(official_response)),
    )
    channel = client.post(
        "/api/v1/channels",
        json={
            "name": "Política em Foco",
            "slug": "politica-em-foco",
            "niche": "Política",
            "default_engine": "politics",
        },
    ).json()
    search = client.get("/api/v1/politics/proposals", params={"year": 2026})
    assert search.status_code == 200
    assert search.json()[0]["source_url"].startswith("https://www.camara.leg.br/")

    imported = client.post(
        "/api/v1/politics/projects",
        json={"channel_id": channel["id"], "proposal_id": 123456},
    )
    assert imported.status_code == 201
    project = imported.json()
    assert project["format"] == "vertical"
    assert project["content_type"] == "knowledge"
    assert project["plan"]["origin"] == "OFFICIAL_SOURCE"
    assert project["plan"]["source_refs"][0]["api_url"].endswith("/123456")
    assert len(project["plan"]["source_refs"][0]["source_sha256"]) == 64
    assert "Institui diretrizes" in project["plan"]["scenes"][1]["narration"]
    assert "Apresentação de Proposição" in project["plan"]["scenes"][-1]["narration"]
    assert project["script"]["segments"] == [
        scene["narration"] for scene in project["plan"]["scenes"]
    ]
    assert len(project["edl"]["tracks"]["video"]) == len(project["plan"]["scenes"])
    base = f"/api/v1/projects/{project['id']}"
    claims = client.get(f"{base}/claims").json()
    assert {claim["scene_id"] for claim in claims} == {
        "official-id", "official-summary-1", "official-status",
    }
    assert all(claim["status"] == "REVIEW_REQUIRED" for claim in claims)
    assert all(claim["source_url"] == project["plan"]["source_refs"][0]["url"]
               for claim in claims)
    preview = client.get(f"{base}/preview")
    assert preview.status_code == 200, preview.text
    props = preview.json()["props"]
    assert props["editorial_style"] == "official_politics"
    assert props["official_reference"] == "PL 42/2026"
    assert props["source_checked_at"]
    assert props["accent"] == "#D0E5BC"
    assert [scene["on_screen_text"] for scene in props["scenes"]] == [
        scene["on_screen_text"] for scene in project["plan"]["scenes"]
    ]
    assert [scene["supporting_text"] for scene in props["scenes"]] == [
        scene["narration"] for scene in project["plan"]["scenes"]
    ]

    plan = project["plan"]
    plan["scenes"][0]["narration"] += " Texto revisado."
    updated = client.put(
        f"/api/v1/projects/{project['id']}/plan",
        json={"scenes": plan["scenes"], "hook": plan["hook"], "angle": plan["angle"]},
    )
    assert updated.status_code == 200
    assert updated.json()["plan"]["origin"] == "MANUAL"
    assert updated.json()["plan"]["source_refs"] == plan["source_refs"]
    assert source_label(updated.json()["plan"]) == "Fonte: Câmara dos Deputados"
    revised_preview = client.get(f"{base}/preview")
    assert revised_preview.status_code == 200, revised_preview.text
    assert revised_preview.json()["props"]["editorial_style"] == "official_politics"
    assert revised_preview.json()["props"]["scenes"][0]["supporting_text"].endswith(
        "Texto revisado."
    )
    assert client.post(f"/api/v1/projects/{project['id']}/voice").status_code == 202
    assert client.post(f"/api/v1/projects/{project['id']}/render").status_code == 409
    with SessionLocal() as db:
        stored = db.get(Project, project["id"])
        assert stored is not None
        stored.status = ProjectStatus.QC.value
        db.commit()
    render_dir = tmp_path / "renders"
    render_dir.mkdir()
    (render_dir / f"{project['id']}.mp4").write_bytes(b"synthetic-review-gate")
    review = {
        "source_urls": [claims[0]["source_url"]],
        "facts_confirmed": True, "rights_confirmed": True,
        "notes": "Fonte e contexto conferidos", "caption": "Legenda de teste.",
    }
    assert client.post(f"{base}/review", json=review).status_code == 409
    for claim in claims:
        approved = client.post(f"{base}/claims/{claim['id']}/approve", json={
            "expected_revision": claim["revision"], "source_opened": True,
            "excerpt_matches": True, "context_checked": True,
        })
        assert approved.status_code == 200, approved.text
    assert client.post(f"{base}/review", json=review).status_code == 200
    package = client.get(f"{base}/export")
    assert package.status_code == 200
    with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["source_refs"][0]["source_sha256"] == (
        project["plan"]["source_refs"][0]["source_sha256"]
    )
    assert len(manifest["knowledge_claims"]) == len(claims)


def test_official_politics_rejects_wrong_channel_and_offline_source(
    client: TestClient, monkeypatch
) -> None:
    channel = client.post(
        "/api/v1/channels",
        json={"name": "Música", "slug": "musica", "niche": "Música", "default_engine": "music"},
    ).json()
    assert client.post(
        "/api/v1/politics/projects",
        json={"channel_id": channel["id"], "proposal_id": 123456},
    ).status_code == 422

    def offline():
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(official_politics, "official_client", offline)
    response = client.get("/api/v1/politics/proposals", params={"year": 2026})
    assert response.status_code == 503
    assert client.get("/api/v1/projects").json() == []


def test_caption_shortening_keeps_whole_words() -> None:
    result = official_politics.short_caption(
        "Institui diretrizes para investimentos importantes em infraestrutura", 42
    )
    assert result == "Institui diretrizes para investimentos…"
    assert (
        official_politics.summary_headline(
            "Institui a Lei Amapá Tucuju, estabelece diretrizes para investimentos"
        )
        == "Institui a Lei Amapá Tucuju"
    )


def test_official_import_rejects_missing_record_date(
    client: TestClient, monkeypatch
) -> None:
    def missing_date(request: httpx.Request) -> httpx.Response:
        body = official_response(request).json()
        body["dados"]["dataApresentacao"] = ""
        return httpx.Response(200, json=body)

    monkeypatch.setattr(
        official_politics, "official_client",
        lambda: httpx.Client(transport=httpx.MockTransport(missing_date)),
    )
    channel = client.post("/api/v1/channels", json={
        "name": "Política", "slug": "politica", "niche": "Política",
        "default_engine": "politics",
    }).json()
    assert client.post("/api/v1/politics/projects", json={
        "channel_id": channel["id"], "proposal_id": 123456,
    }).status_code == 503
    assert client.get("/api/v1/projects").json() == []


def test_official_summary_chunks_fit_individual_claims() -> None:
    chunks = official_politics._summary_chunks("diretrizes para acesso a dados " * 35)
    assert len(chunks) > 2
    assert all(len(chunk) <= 260 for chunk in chunks)
    assert " ".join(chunks) == ("diretrizes para acesso a dados " * 35).strip()


def test_long_official_summary_creates_reviewable_claims(
    client: TestClient, monkeypatch
) -> None:
    def long_summary(request: httpx.Request) -> httpx.Response:
        body = official_response(request).json()
        body["dados"]["ementa"] = "diretrizes para acesso a dados " * 35
        return httpx.Response(200, json=body)

    monkeypatch.setattr(
        official_politics, "official_client",
        lambda: httpx.Client(transport=httpx.MockTransport(long_summary)),
    )
    channel = client.post("/api/v1/channels", json={
        "name": "Política", "slug": "politica", "niche": "Política",
        "default_engine": "politics",
    }).json()
    response = client.post("/api/v1/politics/projects", json={
        "channel_id": channel["id"], "proposal_id": 123456,
    })
    assert response.status_code == 201, response.text
    claims = client.get(f"/api/v1/projects/{response.json()['id']}/claims").json()
    assert len(claims) > 4
    assert all(len(claim["text"]) <= 300 and len(claim["support_excerpt"]) <= 500
               for claim in claims)
