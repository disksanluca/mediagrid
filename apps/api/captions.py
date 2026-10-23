"""Validated local word timing, editable cues, and sidecar subtitles."""

import json
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from .config import get_settings


class Word(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=200)
    confidence: float | None = Field(default=None, ge=0, le=1)
    speaker_id: str | None = Field(default=None, max_length=80)
    edited: bool = False

    @model_validator(mode="after")
    def valid_span(self) -> "Word":
        if self.end_ms <= self.start_ms or not self.text.strip():
            raise ValueError("Word needs text and positive time span")
        return self


class Cue(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=250)
    speaker_id: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def valid_span(self) -> "Cue":
        if self.end_ms <= self.start_ms or not self.text.strip():
            raise ValueError("Caption needs text and positive time span")
        return self


def validate_timing(words: list[Word], cues: list[Cue], duration_ms: int) -> None:
    for collection, label in ((words, "Word"), (cues, "Caption")):
        if any(item.end_ms > duration_ms for item in collection):
            raise ValueError(f"{label} exceeds source duration")
        if any(right.start_ms < left.start_ms for left, right in zip(
            collection, collection[1:], strict=False
        )):
            raise ValueError(f"{label}s must be chronological")
    if any(right.start_ms < left.end_ms for left, right in zip(
        cues, cues[1:], strict=False
    )):
        raise ValueError("Caption cues must not overlap")


def group_words(words: list[Word]) -> list[Cue]:
    groups: list[list[Word]] = []
    current: list[Word] = []
    for word in words:
        text = " ".join(part.text.strip() for part in [*current, word])
        if current and (
            len(text) > 42 or word.end_ms - current[0].start_ms > 3500
            or word.start_ms - current[-1].end_ms > 500
        ):
            groups.append(current)
            current = []
        current.append(word)
        if word.text.rstrip().endswith((".", "?", "!")):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return [Cue(
        start_ms=group[0].start_ms, end_ms=group[-1].end_ms,
        text=" ".join(word.text.strip() for word in group),
        speaker_id=group[0].speaker_id,
    ) for group in groups]


def stamp(ms: int, sep: str) -> str:
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}{sep}{millis:03}"


def to_srt(cues: list[Cue]) -> str:
    return "\n\n".join(
        f"{index}\n{stamp(cue.start_ms, ',')} --> {stamp(cue.end_ms, ',')}\n{cue.text}"
        for index, cue in enumerate(cues, 1)
    ) + ("\n" if cues else "")


def to_vtt(cues: list[Cue]) -> str:
    blocks = "\n\n".join(
        f"{stamp(cue.start_ms, '.')} --> {stamp(cue.end_ms, '.')}\n{cue.text}"
        for cue in cues
    )
    return "WEBVTT\n\n" + blocks + ("\n" if cues else "")


def probe_media(path: Path) -> tuple[int, bool]:
    """Return real duration and whether an audio stream exists."""
    ffprobe = str(get_settings().mediagrid_ffprobe_path or "ffprobe")
    try:
        result = subprocess.run([
            ffprobe, "-v", "error", "-show_entries", "format=duration:stream=codec_type",
            "-of", "json", str(path.resolve()),
        ], capture_output=True, text=True, check=True, timeout=120)
        data = json.loads(result.stdout)
        duration_ms = round(float(data["format"]["duration"]) * 1000)
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as exc:
        raise ValueError("Could not probe local media") from exc
    if duration_ms <= 0:
        raise ValueError("Media duration is invalid")
    has_audio = any(item.get("codec_type") == "audio" for item in data.get("streams", []))
    return duration_ms, has_audio
