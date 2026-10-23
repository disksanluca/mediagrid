"""Source-backed geography drafts from IBGE Localidades API v1.0.0."""

import hashlib
import json
import unicodedata
from datetime import UTC, datetime

import httpx

from .models import Channel, KnowledgeClaim, Project, ProjectStatus
from .schemas import ContentPlan, Scene
from .services import record_event

BASE_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
MAX_CATALOGUE_BYTES = 4_000_000


def ibge_client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(20, connect=5), follow_redirects=False)


def _plain(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(character for character in normalized if not unicodedata.combining(character))


def _municipality(raw: object) -> dict[str, str | int]:
    if not isinstance(raw, dict):
        raise ValueError("Invalid IBGE municipality")
    fields = {
        "id": raw.get("municipio-id"),
        "name": raw.get("municipio-nome"),
        "state_code": raw.get("UF-sigla"),
        "state_name": raw.get("UF-nome"),
        "region_name": raw.get("regiao-nome"),
        "immediate_name": raw.get("regiao-imediata-nome"),
        "intermediate_name": raw.get("regiao-intermediaria-nome"),
    }
    identifier = fields["id"]
    if not isinstance(identifier, int) or identifier <= 0:
        raise ValueError("Invalid IBGE municipality identifier")
    if any(
        not isinstance(value, str) or not value.strip() or len(value) > 150
        for key, value in fields.items()
        if key != "id"
    ):
        raise ValueError("Incomplete IBGE municipality")
    return {
        **fields,
        "source_url": f"{BASE_URL}/{identifier}?view=nivelado",
    }


def _response_data(response: httpx.Response, max_bytes: int) -> object:
    response.raise_for_status()
    if len(response.content) > max_bytes:
        raise ValueError("IBGE response is too large")
    return response.json()


def search_municipalities(query: str) -> list[dict[str, str | int]]:
    needle = _plain(query.strip())
    if len(needle) < 3:
        raise ValueError("Use at least three characters")
    with ibge_client() as client:
        response = client.get(BASE_URL, params={"view": "nivelado"})
        data = _response_data(response, MAX_CATALOGUE_BYTES)
    if not isinstance(data, list):
        raise ValueError("Unexpected IBGE municipality list")
    matches = [
        _municipality(item)
        for item in data
        if isinstance(item, dict)
        and isinstance(item.get("municipio-nome"), str)
        and needle in _plain(item["municipio-nome"])
    ]
    return sorted(
        matches,
        key=lambda item: (
            _plain(str(item["name"])) != needle,
            not _plain(str(item["name"])).startswith(needle),
            _plain(str(item["name"])),
            str(item["state_code"]),
        ),
    )[:12]


def fetch_municipality(identifier: int) -> dict[str, str | int]:
    with ibge_client() as client:
        data = _response_data(
            client.get(f"{BASE_URL}/{identifier}", params={"view": "nivelado"}), 20_000
        )
    municipality = _municipality(data)
    if municipality["id"] != identifier:
        raise ValueError("IBGE municipality identifier mismatch")
    return municipality


def import_municipality(db, channel: Channel, municipality: dict[str, str | int]) -> Project:
    name = str(municipality["name"])
    state = str(municipality["state_code"])
    project = Project(
        channel_id=channel.id,
        title=f"{name} ({state}) — regiões do IBGE",
        topic=f"Localização administrativa de {name} segundo o IBGE",
        format="vertical",
        content_type="knowledge",
        status=ProjectStatus.SCRIPTED.value,
    )
    db.add(project)
    db.flush()
    scenes = [
        Scene(
            id="ibge-location",
            duration_seconds=8,
            narration=(
                f"Segundo o cadastro de localidades do IBGE, {name} é um município "
                f"de {municipality['state_name']}, {state}."
            ),
            visual_type="headline",
            visual_query=f"{name} {state}",
            on_screen_text=f"{name} · {state}",
            transition="impact",
        ),
        Scene(
            id="ibge-immediate",
            duration_seconds=8,
            narration=(
                f"{name} integra a região geográfica imediata de "
                f"{municipality['immediate_name']}."
            ),
            visual_type="quote",
            visual_query=f"{name} região imediata",
            on_screen_text=f"Região imediata: {municipality['immediate_name']}",
            transition="slide",
        ),
        Scene(
            id="ibge-intermediate",
            duration_seconds=10,
            narration=(
                f"Na divisão do IBGE, a região intermediária é "
                f"{municipality['intermediate_name']}, na Grande Região "
                f"{municipality['region_name']}."
            ),
            visual_type="outro",
            visual_query=f"{name} {municipality['region_name']}",
            on_screen_text=(
                f"{municipality['intermediate_name']} · {municipality['region_name']}"
            ),
            transition="fade",
        ),
    ]
    checked_at = datetime.now(UTC)
    fetched_at = checked_at.isoformat()
    source_snapshot = {key: municipality[key] for key in (
        "id", "name", "state_code", "state_name", "region_name",
        "immediate_name", "intermediate_name",
    )}
    source_digest = hashlib.sha256(json.dumps(
        source_snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    source_url = str(municipality["source_url"])
    source_title = f"IBGE Localidades — {name} ({state})"
    evidence = (
        f"municipio-id: {municipality['id']}; municipio-nome: {name}; "
        f"UF-nome: {municipality['state_name']}; UF-sigla: {state}"
    )
    claims = [
        KnowledgeClaim(project_id=project.id, scene_id=scenes[0].id,
                       text=scenes[0].narration, source_url=source_url,
                       source_title=source_title, published_at=None,
                       source_checked_at=checked_at, support_excerpt=evidence),
        KnowledgeClaim(project_id=project.id, scene_id=scenes[1].id,
                       text=scenes[1].narration, source_url=source_url,
                       source_title=source_title, published_at=None,
                       source_checked_at=checked_at,
                       support_excerpt=f"regiao-imediata-nome: {municipality['immediate_name']}"),
        KnowledgeClaim(project_id=project.id, scene_id=scenes[2].id,
                       text=scenes[2].narration, source_url=source_url,
                       source_title=source_title, published_at=None,
                       source_checked_at=checked_at,
                       support_excerpt=(
                           f"regiao-intermediaria-nome: {municipality['intermediate_name']}; "
                           f"regiao-nome: {municipality['region_name']}"
                       )),
    ]
    db.add_all(claims)
    plan = ContentPlan(
        project_id=project.id,
        engine="geo",
        origin="OFFICIAL_SOURCE",
        hook=scenes[0].narration,
        angle="Localização administrativa no cadastro do IBGE; revisar antes de publicar.",
        target_duration_seconds=round(sum(scene.duration_seconds for scene in scenes)),
        scenes=scenes,
        requires_fact_review=True,
        review_checks=[
            "Conferir nomes e divisão regional no IBGE",
            "Confirmar direitos de mapas ou imagens adicionados",
        ],
        source_refs=[
            {
                "title": source_title,
                "url": source_url,
                "api_url": source_url,
                "fetched_at": fetched_at,
                "snapshot_sha256": source_digest,
            }
        ],
    )
    project.plan = plan.model_dump()
    project.script = {"language": channel.language, "segments": [s.narration for s in scenes]}
    project.edl = {
        "version": 1,
        "format": "vertical",
        "tracks": {
            "video": [
                {
                    "scene_id": s.id,
                    "duration": s.duration_seconds,
                    "visual_type": s.visual_type,
                    "transition": s.transition,
                }
                for s in scenes
            ],
            "audio": [{"scene_id": s.id, "text": s.narration} for s in scenes],
            "captions": [{"scene_id": s.id, "text": s.on_screen_text} for s in scenes],
        },
    }
    record_event(
        db,
        "OFFICIAL_MUNICIPALITY_IMPORTED",
        "project",
        project.id,
        after={"source_url": source_url, "fetched_at": fetched_at,
               "snapshot_sha256": source_digest},
    )
    return project
