"""Read-only Câmara dos Deputados data for source-backed political drafts."""

import hashlib
import json
from datetime import UTC, date, datetime

import httpx

from .models import Channel, KnowledgeClaim, Project, ProjectStatus
from .schemas import ContentPlan, Scene
from .services import record_event

BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"


def short_caption(text: str, limit: int = 60) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:") + "…"


def summary_headline(text: str) -> str:
    first_clause = " ".join(text.split()).split(",", 1)[0].rstrip(" .;:")
    return first_clause if 20 <= len(first_clause) <= 70 else short_caption(text)


def _record_date(value: object) -> date:
    try:
        recorded = date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise ValueError("Câmara record has no valid date") from exc
    if recorded > datetime.now(UTC).date():
        raise ValueError("Câmara record date is in the future")
    return recorded


def _summary_chunks(summary: str, limit: int = 260) -> list[str]:
    chunks: list[str] = []
    current = ""
    for word in summary.split():
        if len(word) > limit:
            raise ValueError("Câmara summary contains an oversized token")
        candidate = f"{current} {word}".strip()
        if len(candidate) > limit:
            chunks.append(current)
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def official_client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(15, connect=5), follow_redirects=False)


def _data(response: httpx.Response) -> object:
    response.raise_for_status()
    if len(response.content) > 1_000_000:
        raise ValueError("Official response is too large")
    body = response.json()
    if not isinstance(body, dict) or "dados" not in body:
        raise ValueError("Unexpected Câmara response")
    return body["dados"]


def _proposal(raw: object) -> dict[str, str | int]:
    if not isinstance(raw, dict):
        raise ValueError("Invalid Câmara proposition")
    identifier = raw.get("id")
    number = raw.get("numero")
    year = raw.get("ano")
    summary = raw.get("ementa")
    if (
        not isinstance(identifier, int)
        or not isinstance(number, int)
        or not isinstance(year, int)
        or raw.get("siglaTipo") != "PL"
        or not isinstance(summary, str)
        or not summary.strip()
    ):
        raise ValueError("Incomplete Câmara proposition")
    return {
        "id": identifier,
        "number": number,
        "year": year,
        "summary": summary.strip(),
        "presented_at": str(raw.get("dataApresentacao") or ""),
        "source_url": (
            "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao"
            f"?idProposicao={identifier}"
        ),
        "api_url": f"{BASE_URL}/proposicoes/{identifier}",
    }


def search_proposals(query: str, year: int) -> list[dict[str, str | int]]:
    params: dict[str, str | int] = {
        "siglaTipo": "PL",
        "ano": year,
        "ordenarPor": "id",
        "ordem": "DESC",
        "itens": 10,
    }
    if query:
        params["ementa"] = query
    with official_client() as client:
        data = _data(client.get(f"{BASE_URL}/proposicoes", params=params))
    if not isinstance(data, list):
        raise ValueError("Unexpected Câmara proposition list")
    return [_proposal(item) for item in data]


def fetch_proposal(identifier: int) -> tuple[dict[str, str | int], dict]:
    with official_client() as client:
        data = _data(client.get(f"{BASE_URL}/proposicoes/{identifier}"))
    proposal = _proposal(data)
    if proposal["id"] != identifier:
        raise ValueError("Câmara proposition identifier mismatch")
    status = data.get("statusProposicao") if isinstance(data, dict) else None
    return proposal, status if isinstance(status, dict) else {}


def build_politics_plan(
    project: Project, channel: Channel, proposal: dict[str, str | int], status: dict
) -> ContentPlan:
    label = f"PL {proposal['number']}/{proposal['year']}"
    presented = str(proposal["presented_at"])[:10]
    introduction = f"A Câmara dos Deputados registra o {label}"
    if presented:
        introduction += f", apresentado em {presented[8:10]}/{presented[5:7]}/{presented[:4]}"
    introduction += "."
    summary = str(proposal["summary"])
    status_text = status.get("descricaoTramitacao") or status.get("descricaoSituacao")
    status_date = str(status.get("dataHora") or "")[:10]
    if isinstance(status_text, str) and 0 < len(status_text.strip()) <= 240 and status_date:
        close = (
            f"Em {status_date[8:10]}/{status_date[5:7]}/{status_date[:4]}, "
            f"a tramitação registrada era: {status_text.strip()}."
        )
    else:
        close = "Confira a tramitação atual no registro oficial antes de publicar."
    scenes = [
        Scene(
            id="official-id",
            duration_seconds=max(6, round(len(introduction.split()) / 2.2 + 2)),
            narration=introduction,
            visual_type="headline",
            visual_query=label,
            on_screen_text=label,
            transition="impact",
        ),
    ]
    for index, excerpt in enumerate(_summary_chunks(summary)):
        narration = f"A ementa oficial informa: {excerpt}" if index == 0 else excerpt
        scenes.append(
            Scene(
                id=f"official-summary-{index + 1}",
                duration_seconds=max(8, min(60, round(len(narration.split()) / 2.2 + 2))),
                narration=narration,
                visual_type="quote",
                visual_query=label,
                on_screen_text=(
                    summary_headline(excerpt) if index == 0 else short_caption(excerpt)
                ),
                transition="slide",
            )
        )
    scenes.append(
        Scene(
            id="official-status",
            duration_seconds=max(6, min(60, round(len(close.split()) / 2.2 + 2))),
            narration=close,
            visual_type="outro",
            visual_query=label,
            on_screen_text=(
                short_caption(status_text)
                if isinstance(status_text, str)
                and 0 < len(status_text.strip()) <= 240
                and status_date
                else "Confira a tramitação"
            ),
            transition="fade",
        )
    )
    fetched_at = datetime.now(UTC).isoformat()
    source_digest = hashlib.sha256(json.dumps(
        {"proposal": proposal, "status": status}, ensure_ascii=False,
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return ContentPlan(
        project_id=project.id,
        engine="politics",
        origin="OFFICIAL_SOURCE",
        hook=introduction,
        angle="Resumo fiel do registro da Câmara; revisar contexto e tramitação.",
        target_duration_seconds=round(sum(scene.duration_seconds for scene in scenes)),
        scenes=scenes,
        requires_fact_review=True,
        review_checks=[
            "Confirmar tramitação atual na fonte",
            "Distinguir proposta de lei em vigor",
            "Revisar contexto e direitos de mídia",
        ],
        source_refs=[
            {
                "title": f"Câmara dos Deputados — {label}",
                "url": str(proposal["source_url"]),
                "api_url": str(proposal["api_url"]),
                "fetched_at": fetched_at,
                "source_sha256": source_digest,
            }
        ],
    )


def import_proposal(db, channel: Channel, proposal: dict[str, str | int], status: dict) -> Project:
    label = f"PL {proposal['number']}/{proposal['year']}"
    if len(str(proposal["presented_at"])) > 32:
        raise ValueError("Câmara presentation date is too long")
    presented = _record_date(proposal["presented_at"])
    status_text = status.get("descricaoTramitacao") or status.get("descricaoSituacao")
    if status.get("dataHora") and len(str(status["dataHora"])) > 32:
        raise ValueError("Câmara status date is too long")
    status_date = (_record_date(status["dataHora"])
                   if isinstance(status_text, str) and 0 < len(status_text.strip()) <= 240
                   and status.get("dataHora") else None)
    project = Project(
        channel_id=channel.id,
        title=f"{label}: {str(proposal['summary'])[:150]}",
        topic=str(proposal["summary"]),
        format="vertical",
        content_type="knowledge",
        status=ProjectStatus.SCRIPTED.value,
    )
    db.add(project)
    db.flush()
    plan = build_politics_plan(project, channel, proposal, status)
    source_title = f"Câmara dos Deputados — {label}"
    source_url = str(proposal["source_url"])
    intro_evidence = (f"siglaTipo: PL; numero: {proposal['number']}; "
                      f"ano: {proposal['year']}; "
                      f"dataApresentacao: {proposal['presented_at']}")
    claims = [KnowledgeClaim(
        project_id=project.id, scene_id="official-id",
        text=plan.scenes[0].narration, source_url=source_url,
        source_title=source_title, published_at=presented,
        support_excerpt=intro_evidence,
    )]
    for scene in plan.scenes[1:-1]:
        excerpt = scene.narration.removeprefix("A ementa oficial informa: ")
        claims.append(KnowledgeClaim(
            project_id=project.id, scene_id=scene.id,
            text=scene.narration, source_url=source_url,
            source_title=source_title, published_at=presented,
            support_excerpt=excerpt,
        ))
    if status_date is not None:
        claims.append(KnowledgeClaim(
            project_id=project.id, scene_id="official-status",
            text=plan.scenes[-1].narration, source_url=source_url,
            source_title=source_title, published_at=status_date,
            support_excerpt=(f"descricaoTramitacao: {status_text.strip()}; "
                             f"dataHora: {status['dataHora']}"),
        ))
    db.add_all(claims)
    project.plan = plan.model_dump()
    project.script = {"language": channel.language, "segments": [s.narration for s in plan.scenes]}
    project.edl = {
        "version": 1,
        "format": "vertical",
        "tracks": {
            "video": [
                {"scene_id": s.id, "duration": s.duration_seconds,
                 "visual_type": s.visual_type, "transition": s.transition}
                for s in plan.scenes
            ],
            "audio": [{"scene_id": s.id, "text": s.narration} for s in plan.scenes],
            "captions": [{"scene_id": s.id, "text": s.on_screen_text} for s in plan.scenes],
        },
    }
    record_event(
        db,
        "OFFICIAL_PROPOSAL_IMPORTED",
        "project",
        project.id,
        after={
            "source_url": proposal["source_url"],
            "fetched_at": plan.source_refs[0]["fetched_at"],
            "source_sha256": plan.source_refs[0]["source_sha256"],
            "claims_review_required": len(claims),
        },
    )
    return project
