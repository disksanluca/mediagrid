"""Shared, deterministic props for the browser preview and local renderer."""

import json
import re
import subprocess
import wave
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
    if overlays:
        props["overlays"] = [
            {
                "id": item.id, "start_ms": item.start_ms,
                "duration_ms": item.duration_ms, "z_index": item.z_index,
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
