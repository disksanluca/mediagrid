import httpx
from fastapi.testclient import TestClient

from apps.api import official_politics


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
    client: TestClient, monkeypatch
) -> None:
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
    assert project["plan"]["origin"] == "OFFICIAL_SOURCE"
    assert project["plan"]["source_refs"][0]["api_url"].endswith("/123456")
    assert "Institui diretrizes" in project["plan"]["scenes"][1]["narration"]
    assert "Apresentação de Proposição" in project["plan"]["scenes"][-1]["narration"]
    assert project["script"]["segments"] == [
        scene["narration"] for scene in project["plan"]["scenes"]
    ]
    assert len(project["edl"]["tracks"]["video"]) == len(project["plan"]["scenes"])

    plan = project["plan"]
    plan["scenes"][0]["narration"] += " Texto revisado."
    updated = client.put(
        f"/api/v1/projects/{project['id']}/plan",
        json={"scenes": plan["scenes"], "hook": plan["hook"], "angle": plan["angle"]},
    )
    assert updated.status_code == 200
    assert updated.json()["plan"]["origin"] == "MANUAL"
    assert updated.json()["plan"]["source_refs"] == plan["source_refs"]
    assert client.post(f"/api/v1/projects/{project['id']}/voice").status_code == 202
    assert client.post(f"/api/v1/projects/{project['id']}/render").status_code == 202


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
