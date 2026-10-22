import httpx
from fastapi.testclient import TestClient

from apps.api import official_geo
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
    assert len(project["plan"]["scenes"]) == 3
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
