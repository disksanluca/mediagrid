"""Source-backed MusicBrainz release-group drafts; no copyrighted media is fetched."""

import hashlib
import json
import re
import threading
import time
from datetime import UTC, date, datetime
from uuid import UUID

import httpx

from .models import Channel, KnowledgeClaim, Project, ProjectStatus
from .schemas import ContentPlan, Scene
from .services import record_event

BASE_URL = "https://musicbrainz.org/ws/2/release-group"
ABOUT_URL = "https://musicbrainz.org/doc/About"
MAX_RESPONSE_BYTES = 200_000
_REQUEST_LOCK = threading.Lock()
_last_request = 0.0


def musicbrainz_client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(20, connect=5), follow_redirects=False,
        headers={"User-Agent": "MediaGrid/0.1 (https://github.com/disksanluca/mediagrid)",
                 "Accept": "application/json"},
    )


def _request(url: str, params: dict[str, str | int]) -> dict:
    global _last_request
    # MusicBrainz asks ordinary clients to average at most one request per second.
    with _REQUEST_LOCK:
        remaining = 1.1 - (time.monotonic() - _last_request)
        if remaining > 0:
            time.sleep(remaining)
        _last_request = time.monotonic()
        with musicbrainz_client() as client:
            with client.stream("GET", url, params=params) as response:
                response.raise_for_status()
                chunks = bytearray()
                for chunk in response.iter_bytes():
                    if len(chunks) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise ValueError("MusicBrainz response is too large")
                    chunks.extend(chunk)
    body = json.loads(chunks)
    if not isinstance(body, dict):
        raise ValueError("Unexpected MusicBrainz response")
    return body


def _safe(value: object, limit: int) -> str:
    if (not isinstance(value, str) or not 1 <= len(value.strip()) <= limit
            or any(ord(char) < 32 for char in value)):
        raise ValueError("Invalid MusicBrainz text")
    return value.strip()


def _release_group(raw: dict) -> dict[str, str]:
    identifier = str(UUID(str(raw.get("id"))))
    title = _safe(raw.get("title"), 140)
    credits = raw.get("artist-credit")
    if not isinstance(credits, list) or not 1 <= len(credits) <= 8:
        raise ValueError("MusicBrainz artist credit is missing")
    artist = "".join(
        _safe(part.get("name"), 100) + str(part.get("joinphrase") or "")
        for part in credits if isinstance(part, dict)
    ).strip()
    artist = _safe(artist, 180)
    first_date = raw.get("first-release-date") or ""
    if not isinstance(first_date, str) or (
        first_date and not re.fullmatch(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", first_date)
    ):
        raise ValueError("Invalid first release date")
    if first_date and len(first_date) >= 7 and not 1 <= int(first_date[5:7]) <= 12:
        raise ValueError("Invalid first release month")
    if first_date and len(first_date) == 10:
        try:
            date.fromisoformat(first_date)
        except ValueError as exc:
            raise ValueError("Invalid first release day") from exc
    primary_type = raw.get("primary-type") or ""
    if primary_type and primary_type not in {"Album", "Single", "EP", "Broadcast", "Other"}:
        raise ValueError("Unexpected release group type")
    return {"id": identifier, "title": title, "artist": artist,
            "first_release_date": first_date, "primary_type": primary_type,
            "source_url": f"https://musicbrainz.org/release-group/{identifier}"}


def search_release_groups(query: str) -> list[dict[str, str]]:
    query = query.strip()
    if not 3 <= len(query) <= 80:
        raise ValueError("Use 3 to 80 characters for a MusicBrainz search")
    body = _request(BASE_URL + "/", {"query": query, "fmt": "json", "limit": 10})
    rows = body.get("release-groups")
    if not isinstance(rows, list):
        raise ValueError("MusicBrainz search has no release groups")
    records = []
    for raw in rows[:10]:
        if not isinstance(raw, dict):
            continue
        try:
            records.append(_release_group(raw))
        except ValueError:
            continue
    return records


def fetch_release_group(identifier: UUID) -> tuple[dict[str, str], datetime]:
    body = _request(f"{BASE_URL}/{identifier}", {"inc": "artist-credits", "fmt": "json"})
    record = _release_group(body)
    if record["id"] != str(identifier):
        raise ValueError("MusicBrainz release group identifier mismatch")
    return record, datetime.now(UTC)


def import_release_group(db, channel: Channel, record: dict[str, str],
                         checked_at: datetime) -> Project:
    title, artist = record["title"], record["artist"]
    source_url = record["source_url"]
    first_date = record["first_release_date"]
    snapshot = {key: record[key] for key in (
        "id", "title", "artist", "first_release_date", "primary_type",
    )}
    digest = hashlib.sha256(json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    project = Project(
        channel_id=channel.id, title=f"{title} — ficha musical",
        topic=f"Metadados do grupo de lançamentos {title}, crédito a {artist}",
        format="vertical", content_type="knowledge", status=ProjectStatus.SCRIPTED.value,
    )
    db.add(project)
    db.flush()
    date_narration = (
        f"O campo de primeira data cadastrada para {title} mostra {first_date}."
        if first_date else f"O registro de {title} não informa uma primeira data."
    )
    scenes = [
        Scene(id="music-identity", duration_seconds=9,
              narration=(f"No MusicBrainz, o grupo de lançamentos {title} tem "
                         f"crédito a {artist}."),
              visual_type="headline", visual_query=f"{title} {artist}",
              on_screen_text=title, transition="impact"),
        Scene(id="music-date", duration_seconds=8, narration=date_narration,
              visual_type="quote", visual_query=title,
              on_screen_text=title,
              transition="slide"),
        Scene(id="music-rights", duration_seconds=9,
              narration=("O MusicBrainz fornece metadados, não o áudio da obra. "
                         "Confira créditos e direitos de capa e trechos antes de publicar."),
              visual_type="outro", visual_query="direitos de música",
              on_screen_text="Metadados ≠ licença de áudio ou capa", transition="fade"),
    ]
    claims = [
        KnowledgeClaim(project_id=project.id, scene_id=scenes[0].id,
                       text=scenes[0].narration, source_url=source_url,
                       source_title=f"MusicBrainz — {title}", published_at=None,
                       source_checked_at=checked_at,
                       support_excerpt=(
                           f"id: {record['id']}; title: {title}; artist-credit: {artist}"
                       )),
        KnowledgeClaim(project_id=project.id, scene_id=scenes[1].id,
                       text=scenes[1].narration, source_url=source_url,
                       source_title=f"MusicBrainz — {title}", published_at=None,
                       source_checked_at=checked_at,
                       support_excerpt=(
                           f"id: {record['id']}; first-release-date: {first_date or '(empty)'}"
                       )),
        KnowledgeClaim(project_id=project.id, scene_id=scenes[2].id,
                       text=scenes[2].narration, source_url=ABOUT_URL,
                       source_title="MusicBrainz — About", published_at=None,
                       source_checked_at=None,
                       support_excerpt=(
                           "MusicBrainz does not store or have access to music recordings."
                       )),
    ]
    db.add_all(claims)
    plan = ContentPlan(
        project_id=project.id, engine="music", origin="OFFICIAL_SOURCE",
        hook=scenes[0].narration,
        angle="Ficha de metadados comunitários; sem inferir relevância ou usar mídia protegida.",
        target_duration_seconds=26, scenes=scenes, requires_fact_review=True,
        review_checks=["Conferir identidade, crédito e data no MusicBrainz",
                       "Confirmar direitos de áudio, capa e trechos adicionados",
                       "Revisar texto e contexto antes de exportar"],
        source_refs=[{"title": f"MusicBrainz — {title}", "url": source_url,
                      "api_url": f"{BASE_URL}/{record['id']}?inc=artist-credits&fmt=json",
                      "fetched_at": checked_at.isoformat(), "snapshot_sha256": digest,
                      "record_id": record["id"], "record_title": title,
                      "artist": artist, "first_release_date": first_date,
                      "primary_type": record["primary_type"],
                      "data_license": "CC0 core data"},
                     {"title": "MusicBrainz — About", "url": ABOUT_URL}],
    )
    project.plan = plan.model_dump()
    project.script = {"language": channel.language,
                      "segments": [scene.narration for scene in scenes]}
    project.edl = {"version": 1, "format": "vertical", "tracks": {
        "video": [{"scene_id": scene.id, "duration": scene.duration_seconds,
                   "visual_type": scene.visual_type, "transition": scene.transition}
                  for scene in scenes],
        "audio": [{"scene_id": scene.id, "text": scene.narration} for scene in scenes],
        "captions": [{"scene_id": scene.id, "text": scene.on_screen_text}
                     for scene in scenes],
    }}
    record_event(db, "MUSICBRAINZ_RELEASE_GROUP_IMPORTED", "project", project.id,
                 after={"source_url": source_url, "fetched_at": checked_at.isoformat(),
                        "snapshot_sha256": digest})
    return project
