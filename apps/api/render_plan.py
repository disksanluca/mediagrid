"""Shared, deterministic props for the browser preview and local renderer."""

import hashlib
import json
import re
import subprocess
import wave
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from .config import get_settings
from .edl_v2 import TimelineItem
from .models import Channel, Project


def source_label(plan: dict | None) -> str | None:
    for source in (plan or {}).get("source_refs", []):
        if not isinstance(source, dict):
            continue
        url = source.get("api_url")
        if isinstance(url, str) and urlparse(url).hostname == "dadosabertos.camara.leg.br":
            return "Fonte: Câmara dos Deputados"
        if isinstance(url, str) and urlparse(url).hostname == "servicodados.ibge.gov.br":
            return "Fonte: IBGE"
        if isinstance(url, str) and urlparse(url).hostname == "wikimedia.org":
            return "Fonte: Wikimedia Analytics"
    return None


def fit_video_to_voice(
    video: list[dict], audio: list[dict], voice: Path | None
) -> tuple[list[dict], float]:
    """Keep every narration audible when local TTS runs longer than estimates."""
    tracks = [item.copy() for item in video]
    planned = sum(float(item["duration"]) for item in tracks)
    if voice is None:
        return tracks, planned
    try:
        with wave.open(str(voice), "rb") as wav:
            voice_seconds = wav.getnframes() / wav.getframerate()
    except (OSError, wave.Error, ZeroDivisionError) as exc:
        raise ValueError("Generated voice is not a readable WAV") from exc
    required = voice_seconds + 1.0
    if required > planned:
        weights = [max(1, len(str(item.get("text", "")).split())) for item in audio]
        if len(weights) != len(tracks):
            raise ValueError("Voice and video scene counts do not match")
        total_weight = sum(weights)
        for item, weight in zip(tracks, weights, strict=True):
            item["duration"] = (
                float(item["duration"]) + (required - planned) * weight / total_weight
            )
    return tracks, sum(float(item["duration"]) for item in tracks)


def render_props(
    project: Project,
    channel: Channel | None,
    video_tracks: list[dict],
    overlays: list[TimelineItem],
    sounds: list[TimelineItem],
    video_layers: list[TimelineItem],
) -> dict:
    configured_accent = (channel.brand_profile or {}).get("accent") if channel else None
    accent = (
        configured_accent
        if isinstance(configured_accent, str)
        and re.fullmatch(r"#[0-9a-fA-F]{6}", configured_accent)
        else "#c5ccd6"
    )
    captions = {item["scene_id"]: item["text"] for item in project.edl["tracks"]["captions"]}
    props = {
        "title": project.title,
        "format": project.format,
        "accent": accent,
        "source_label": source_label(project.plan),
        "scenes": [
            dict(item, on_screen_text=captions.get(item["scene_id"]))
            for item in video_tracks
        ],
    }
    plan = project.plan or {}
    if project.format == "vertical" and plan.get("engine") == "politics":
        for source in plan.get("source_refs", []):
            if not isinstance(source, dict):
                continue
            api_url = source.get("api_url")
            if (not isinstance(api_url, str)
                    or urlparse(api_url).hostname != "dadosabertos.camara.leg.br"):
                continue
            reference = re.search(r"\bPL \d{1,6}/\d{4}\b", str(source.get("title", "")))
            fetched_at = str(source.get("fetched_at", ""))
            props["editorial_style"] = "official_politics"
            props["official_reference"] = reference.group() if reference else "PROPOSIÇÃO"
            spoken = {
                item["scene_id"]: item["text"]
                for item in project.edl["tracks"]["audio"]
                if isinstance(item.get("scene_id"), str)
                and isinstance(item.get("text"), str)
            }
            for scene in props["scenes"]:
                narration = spoken.get(scene["scene_id"], "").strip()
                if 0 < len(narration) <= 240:
                    scene["supporting_text"] = narration
            if re.match(r"^\d{4}-\d{2}-\d{2}T", fetched_at):
                props["source_checked_at"] = fetched_at[:10]
            if accent == "#c5ccd6":
                props["accent"] = "#D0E5BC"
            break
    if (project.format == "vertical" and plan.get("engine") == "trends"
            and plan.get("origin") == "OFFICIAL_SOURCE"):
        for source in plan.get("source_refs", []):
            if not isinstance(source, dict):
                continue
            api_url = source.get("api_url")
            article = source.get("article")
            title = source.get("article_title")
            views = source.get("views")
            rank = source.get("rank")
            observed_on = source.get("observed_on")
            digest = source.get("snapshot_sha256")
            display_day = (f"{observed_on[8:10]}/{observed_on[5:7]}/"
                           f"{observed_on[:4]}") if isinstance(observed_on, str) else ""
            views_text = f"{int(views):,}".replace(",", ".") if (
                isinstance(views, str) and re.fullmatch(r"[1-9]\d{0,11}", views)) else ""
            expected_title = (f"{title[:50]}{'…' if len(title) > 50 else ''}"
                              if isinstance(title, str) else "")
            if (not isinstance(api_url, str)
                    or urlparse(api_url).hostname != "wikimedia.org"
                    or not isinstance(article, str) or not 0 < len(article) <= 140
                    or not isinstance(title, str) or not 0 < len(title) <= 140
                    or title != article.replace("_", " ")
                    or not isinstance(views, str) or not re.fullmatch(r"[1-9]\d{0,11}", views)
                    or not isinstance(rank, str) or not re.fullmatch(r"[1-9]\d{0,3}", rank)
                    or not isinstance(observed_on, str)
                    or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", observed_on)
                    or not isinstance(digest, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", digest)
                    or captions.get("wiki-views") != (
                        f"{expected_title}\n{views_text} visualizações · {display_day}")
                    or captions.get("wiki-rank") != f"Posição {rank} · Wikipédia PT"
                    or captions.get("wiki-limits") != "Sinal de leitura, não audiência social"):
                continue
            try:
                date.fromisoformat(observed_on)
            except ValueError:
                continue
            if api_url != (
                "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
                "pt.wikipedia.org/all-access/"
                f"{observed_on[:4]}/{observed_on[5:7]}/{observed_on[8:10]}"
            ):
                continue
            snapshot = {
                "project": "pt.wikipedia", "access": "all-access",
                "day": observed_on, "article": article,
                "views": int(views), "rank": int(rank),
            }
            actual_digest = hashlib.sha256(json.dumps(
                snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")).hexdigest()
            if actual_digest != digest:
                continue
            props.update({
                "editorial_style": "wikimedia_trends",
                "wiki_article": title,
                "wiki_views": int(views),
                "wiki_rank": int(rank),
                "wiki_observed_on": observed_on,
            })
            if accent == "#c5ccd6":
                props["accent"] = "#D0E5BC"
            break
    if overlays:
        props["overlays"] = [
            {
                "id": item.id, "start_ms": item.start_ms,
                "duration_ms": item.duration_ms, "z_index": item.z_index,
                "preset": item.preset,
                **item.params,
            }
            for item in overlays
        ]
    if sounds:
        props["sounds"] = [
            {
                "id": item.id, "start_ms": item.start_ms,
                "duration_ms": item.duration_ms,
                "source_asset_id": item.source_asset_id,
                "source_in_ms": item.source_in_ms,
                "source_out_ms": item.source_out_ms,
                **item.params,
            }
            for item in sounds
        ]
    if video_layers:
        props["video_layers"] = [
            {
                "id": item.id, "start_ms": item.start_ms,
                "duration_ms": item.duration_ms,
                "z_index": item.z_index,
                "source_asset_id": item.source_asset_id,
                "source_in_ms": item.source_in_ms,
                "source_out_ms": item.source_out_ms,
                **item.params,
            }
            for item in video_layers
        ]
    return props


def probe_source(path: Path, kind: str) -> float:
    """Read duration and require the expected stream before preparing a preview."""
    ffprobe = get_settings().mediagrid_ffprobe_path or "ffprobe"
    try:
        result = subprocess.run(
            [str(ffprobe), "-v", "error", "-show_entries",
             "format=duration:stream=codec_type", "-of", "json", str(path)],
            check=True, capture_output=True, text=True,
        )
        info = json.loads(result.stdout)
        duration = float(info.get("format", {}).get("duration", 0))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        raise ValueError("Source media could not be probed") from exc
    if duration <= 0 or not any(
        stream.get("codec_type") == kind for stream in info.get("streams", [])
    ):
        raise ValueError(f"Source media has no valid {kind} stream")
    return duration
