"""Wikimedia page views as a narrowly labeled, source-backed Trends signal."""

import hashlib
import json
import unicodedata
from datetime import UTC, date, datetime
from urllib.parse import quote

import httpx

from .models import Channel, KnowledgeClaim, Project, ProjectStatus
from .schemas import ContentPlan, Scene
from .services import record_event

BASE_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
    "pt.wikipedia.org/all-access"
)
DEFINITION_URL = (
    "https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/"
    "concepts/page-views.html"
)
MAX_RESPONSE_BYTES = 1_000_000


def analytics_client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(20, connect=5), follow_redirects=False,
        headers={"User-Agent": (
            "MediaGrid/0.1 (https://github.com/disksanluca/mediagrid) httpx"
        )},
    )


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _validate_day(day: date) -> None:
    if not date(2015, 7, 1) <= day < datetime.now(UTC).date():
        raise ValueError("Choose a completed day from July 2015 onward")


def source_url(day: date) -> str:
    _validate_day(day)
    return f"{BASE_URL}/{day:%Y/%m/%d}"


def fetch_top(day: date) -> tuple[list[dict[str, str | int]], datetime]:
    url = source_url(day)
    with analytics_client() as client:
        response = client.get(url, headers={"Accept": "application/json"})
    response.raise_for_status()
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise ValueError("Wikimedia response is too large")
    body = response.json()
    if not isinstance(body, dict) or not isinstance(body.get("items"), list):
        raise ValueError("Unexpected Wikimedia response")
    items = body["items"]
    if len(items) != 1 or not isinstance(items[0], dict):
        raise ValueError("Unexpected Wikimedia result count")
    item = items[0]
    if (item.get("project") != "pt.wikipedia"
            or item.get("access") != "all-access"
            or str(item.get("year")) != f"{day:%Y}"
            or str(item.get("month")).zfill(2) != f"{day:%m}"
            or str(item.get("day")).zfill(2) != f"{day:%d}"
            or not isinstance(item.get("articles"), list)):
        raise ValueError("Wikimedia result does not match the requested day")
    records = []
    for raw in item["articles"][:1000]:
        if not isinstance(raw, dict):
            continue
        article, views, rank = (raw.get(key) for key in ("article", "views", "rank"))
        if (not isinstance(article, str) or not article.strip()
                or len(article) > 140 or ":" in article or article == "-"
                or any(ord(char) < 32 for char in article)
                or not isinstance(views, int) or isinstance(views, bool) or views <= 0
                or not isinstance(rank, int) or isinstance(rank, bool) or rank <= 0):
            continue
        records.append({
            "article": article,
            "title": article.replace("_", " "),
            "views": views,
            "rank": rank,
            "day": day.isoformat(),
            "source_url": url,
            "article_url": "https://pt.wikipedia.org/wiki/" + quote(article, safe=""),
        })
    if not records:
        raise ValueError("Wikimedia returned no usable pages")
    return records, datetime.now(UTC)


def search_top(day: date, query: str = "") -> list[dict[str, str | int]]:
    records, _ = fetch_top(day)
    needle = _plain(query.strip())
    return [record for record in records
            if needle in _plain(str(record["title"]))][:20]


def import_page(db, channel: Channel, record: dict[str, str | int],
                checked_at: datetime) -> Project:
    title = str(record["title"])
    views = int(record["views"])
    rank = int(record["rank"])
    day = date.fromisoformat(str(record["day"]))
    display_day = f"{day:%d/%m/%Y}"
    views_text = f"{views:,}".replace(",", ".")
    url = str(record["source_url"])
    snapshot = {
        "project": "pt.wikipedia", "access": "all-access", "day": day.isoformat(),
        "article": str(record["article"]), "views": views, "rank": rank,
    }
    digest = hashlib.sha256(json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    project = Project(
        channel_id=channel.id,
        title=f"{title} — leituras na Wikipédia em {display_day}",
        topic=f"Visualizações do verbete {title} na Wikipédia em português em {display_day}",
        format="vertical", content_type="knowledge", status=ProjectStatus.SCRIPTED.value,
    )
    db.add(project)
    db.flush()
    scenes = [
        Scene(
            id="wiki-views", duration_seconds=9,
            narration=(f"Em {display_day}, o verbete {title} recebeu {views_text} "
                       "visualizações na Wikipédia em português."),
            visual_type="stat", visual_query=title,
            on_screen_text=(f"{title[:50]}{'…' if len(title) > 50 else ''}\n"
                            f"{views_text} visualizações · {display_day}"),
            transition="impact",
        ),
        Scene(
            id="wiki-rank", duration_seconds=8,
            narration=(f"Nesse relatório diário da Wikimedia, a página ficou "
                       f"na posição {rank} entre as mais vistas."),
            visual_type="headline", visual_query=title,
            on_screen_text=f"Posição {rank} · Wikipédia PT", transition="slide",
        ),
        Scene(
            id="wiki-limits", duration_seconds=9,
            narration=("Essa métrica conta acessos à página da Wikipédia, "
                       "não audiência no Instagram. Confira o contexto antes de publicar."),
            visual_type="outro", visual_query="métrica de leitura",
            on_screen_text="Sinal de leitura, não audiência social", transition="fade",
        ),
    ]
    source_title = f"Wikimedia Analytics — páginas mais vistas em {display_day}"
    db.add_all([
        KnowledgeClaim(
            project_id=project.id, scene_id=scenes[0].id, text=scenes[0].narration,
            source_url=url, source_title=source_title, published_at=None,
            source_checked_at=checked_at,
            support_excerpt=(f"project: pt.wikipedia; access: all-access; day: "
                             f"{day.isoformat()}; article: {record['article']}; views: {views}"),
        ),
        KnowledgeClaim(
            project_id=project.id, scene_id=scenes[1].id, text=scenes[1].narration,
            source_url=url, source_title=source_title, published_at=None,
            source_checked_at=checked_at,
            support_excerpt=(f"day: {day.isoformat()}; article: {record['article']}; "
                             f"rank: {rank}; views: {views}"),
        ),
        KnowledgeClaim(
            project_id=project.id, scene_id=scenes[2].id, text=scenes[2].narration,
            source_url=DEFINITION_URL, source_title="Wikimedia Analytics — Page views",
            published_at=None, source_checked_at=None,
            support_excerpt=("A métrica page views mede pedidos de conteúdo de "
                             "páginas Wikimedia; project: pt.wikipedia."),
        ),
    ])
    plan = ContentPlan(
        project_id=project.id, engine="trends", origin="OFFICIAL_SOURCE",
        hook=scenes[0].narration,
        angle="Sinal de leitura na Wikipédia, sem inferir tendência em outras plataformas.",
        target_duration_seconds=26, scenes=scenes, requires_fact_review=True,
        review_checks=[
            "Conferir visualizações, posição e data na API Wikimedia",
            "Não chamar visualizações de interesse geral ou tendência no Instagram",
            "Confirmar contexto e direitos de qualquer mídia acrescentada",
        ],
        source_refs=[
            {"title": source_title, "url": url, "api_url": url,
             "observed_on": day.isoformat(), "fetched_at": checked_at.isoformat(),
             "snapshot_sha256": digest, "data_license": "CC0 1.0",
             "article": str(record["article"]), "article_title": title,
             "views": str(views), "rank": str(rank)},
            {"title": "Wikimedia Analytics — definição de page views",
             "url": DEFINITION_URL},
        ],
    )
    project.plan = plan.model_dump()
    project.script = {"language": channel.language,
                      "segments": [scene.narration for scene in scenes]}
    project.edl = {
        "version": 1, "format": "vertical",
        "tracks": {
            "video": [{"scene_id": scene.id, "duration": scene.duration_seconds,
                       "visual_type": scene.visual_type, "transition": scene.transition}
                      for scene in scenes],
            "audio": [{"scene_id": scene.id, "text": scene.narration} for scene in scenes],
            "captions": [{"scene_id": scene.id, "text": scene.on_screen_text}
                         for scene in scenes],
        },
    }
    record_event(db, "WIKIMEDIA_PAGEVIEWS_IMPORTED", "project", project.id,
                 after={"source_url": url, "observed_on": day.isoformat(),
                        "snapshot_sha256": digest})
    return project
