"""Materialize explainable cut suggestions and render only human-selected cuts."""

import json
import shutil
import subprocess
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.captions import Cue, probe_media, to_srt, validate_timing
from apps.api.clip_suggestions import ANALYSIS_VERSION, suggest_clips
from apps.api.config import get_settings
from apps.api.ingestion import sha256_file
from apps.api.models import Asset, ClipCandidate, Transcript
from apps.api.transcripts import words_for


def clip_output(candidate_id: str, revision: int) -> Path:
    return get_settings().mediagrid_data_dir / "clip-renders" / f"{candidate_id}-r{revision}.mp4"


def analyze_asset(db: Session, asset: Asset, transcript: Transcript) -> dict:
    source = get_settings().mediagrid_data_dir / "assets" / asset.id
    if not source.is_file() or sha256_file(source) != asset.sha256:
        raise ValueError("Clip source is missing or changed")
    if transcript.status != "APPROVED" or transcript.source_sha256 != asset.sha256:
        raise ValueError("Approved source transcript is required")
    duration_ms, has_audio = probe_media(source)
    if not has_audio or duration_ms < 12_000:
        raise ValueError("Clip analysis needs at least 12 seconds of video with audio")
    words = words_for(db, transcript.id)
    if not words:
        raise ValueError("Approved transcript has no words to analyze")
    existing = db.scalars(select(ClipCandidate).where(
        ClipCandidate.asset_id == asset.id,
        ClipCandidate.transcript_revision == transcript.revision,
        ClipCandidate.analysis_version == ANALYSIS_VERSION,
    )).all()
    if existing:
        return {"asset_id": asset.id, "source_sha256": asset.sha256,
                "transcript_revision": transcript.revision, "candidates": len(existing),
                "analysis_version": ANALYSIS_VERSION}
    max_ms = min(60_000, duration_ms)
    suggestions = suggest_clips(
        words, duration_ms, min_ms=12_000,
        target_ms=min(32_000, max_ms), max_ms=max_ms,
    )
    for proposed in suggestions:
        db.add(ClipCandidate(
            asset_id=asset.id, source_sha256=asset.sha256,
            transcript_revision=transcript.revision,
            analysis_version=ANALYSIS_VERSION,
            start_ms=proposed.start_ms, end_ms=proposed.end_ms,
            context_start_ms=proposed.context_start_ms,
            context_end_ms=proposed.context_end_ms,
            word_start_index=proposed.word_start_index,
            word_end_index=proposed.word_end_index,
            score=proposed.score, reason_codes=proposed.reason_codes,
            status="SUGGESTED", aspect="source", focus_x=0.5, focus_y=0.5,
            revision=1,
        ))
    return {"asset_id": asset.id, "source_sha256": asset.sha256,
            "transcript_revision": transcript.revision,
            "candidates": len(suggestions), "analysis_version": ANALYSIS_VERSION,
            "status": "SUGGESTED" if suggestions else "NO_CANDIDATES"}


def video_size(source: Path) -> tuple[int, int]:
    ffprobe = str(get_settings().mediagrid_ffprobe_path or "ffprobe")
    result = subprocess.run([
        ffprobe, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "json", str(source.resolve()),
    ], capture_output=True, text=True, check=True, timeout=120)
    stream = json.loads(result.stdout)["streams"][0]
    return int(stream["width"]), int(stream["height"])


def vertical_crop(source: Path, focus_x: float, focus_y: float) -> str:
    width, height = video_size(source)
    if width * 16 >= height * 9:
        crop_width = min(width, int(height * 9 / 16) // 2 * 2)
        crop_height = height // 2 * 2
    else:
        crop_width = width // 2 * 2
        crop_height = min(height, int(width * 16 / 9) // 2 * 2)
    if crop_width < 2 or crop_height < 2:
        raise ValueError("Video resolution is too small for vertical crop")
    if 1080 / crop_width > 3 or 1920 / crop_height > 3:
        raise ValueError("Source resolution is too low for a 1080x1920 vertical crop")
    x = int((width - crop_width) * focus_x) // 2 * 2
    y = int((height - crop_height) * focus_y) // 2 * 2
    return f"crop={crop_width}:{crop_height}:{x}:{y},scale=1080:1920:flags=lanczos"


def render_selected_clip(asset: Asset, transcript: Transcript,
                         candidate: ClipCandidate, job_id: str) -> dict:
    settings = get_settings()
    source = settings.mediagrid_data_dir / "assets" / asset.id
    if not source.is_file() or sha256_file(source) != asset.sha256:
        raise ValueError("Clip source is missing or changed")
    if asset.rights_status not in {"OWNED", "LICENSED"}:
        raise ValueError("Clip source rights are not confirmed")
    if (candidate.asset_id != asset.id or candidate.source_sha256 != asset.sha256
            or candidate.status != "SELECTED" or transcript.status != "APPROVED"
            or transcript.source_sha256 != asset.sha256
            or candidate.transcript_revision != transcript.revision):
        raise ValueError("Clip selection or caption review changed")
    start_ms = (candidate.selected_start_ms if candidate.selected_start_ms is not None
                else candidate.start_ms)
    end_ms = (candidate.selected_end_ms if candidate.selected_end_ms is not None
              else candidate.end_ms)
    duration_ms, has_audio = probe_media(source)
    if not has_audio or not 0 <= start_ms < end_ms <= duration_ms:
        raise ValueError("Selected clip interval is outside source video/audio")
    cues = [Cue.model_validate(item) for item in transcript.cues_json]
    validate_timing([], cues, duration_ms)
    if any(cue.start_ms < start_ms < cue.end_ms
           or cue.start_ms < end_ms < cue.end_ms for cue in cues):
        raise ValueError("Clip boundary splits an approved caption cue")
    clip_cues = [Cue(start_ms=cue.start_ms - start_ms,
                     end_ms=cue.end_ms - start_ms, text=cue.text,
                     speaker_id=cue.speaker_id)
                 for cue in cues if cue.start_ms >= start_ms and cue.end_ms <= end_ms]
    if not clip_cues:
        raise ValueError("Selected interval has no approved captions")
    output = clip_output(candidate.id, candidate.revision)
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < source.stat().st_size + 256 * 1024 * 1024:
        raise ValueError("Not enough local disk space for clip render")
    scratch = (settings.mediagrid_data_dir / "temp" / f"clip-{job_id}").resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    partial = scratch / "cut.mp4"
    try:
        (scratch / "captions.srt").write_text(to_srt(clip_cues), encoding="utf-8")
        filters = ["subtitles=captions.srt"]
        if candidate.aspect == "vertical":
            filters.insert(0, vertical_crop(source, candidate.focus_x, candidate.focus_y))
            filters[-1] = "subtitles=captions.srt:force_style='MarginV=180'"
        elif candidate.aspect != "source":
            raise ValueError("Unknown clip aspect")
        ffmpeg = str(settings.mediagrid_ffmpeg_path or "ffmpeg")
        command = [
            ffmpeg, "-nostdin", "-y", "-v", "error",
            "-ss", f"{start_ms / 1000:.3f}", "-i", str(source.resolve()),
            "-t", f"{(end_ms - start_ms) / 1000:.3f}",
            "-vf", ",".join(filters), "-map", "0:v:0", "-map", "0:a:0",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", str(partial),
        ]
        rendered = subprocess.run(command, cwd=scratch, capture_output=True, text=True,
                                  timeout=max(300, (end_ms - start_ms) // 1000 * 20))
        if rendered.returncode:
            raise ValueError(f"FFmpeg clip render failed: {rendered.stderr[-1000:]}")
        output_duration, output_audio = probe_media(partial)
        if not output_audio or abs(output_duration - (end_ms - start_ms)) > 500:
            raise ValueError("Clip MP4 has invalid duration or lost audio")
        digest = sha256_file(partial)
        partial.replace(output)
        return {
            "output": str(output), "sha256": digest,
            "source_sha256": asset.sha256, "candidate_id": candidate.id,
            "candidate_revision": candidate.revision,
            "transcript_revision": transcript.revision,
            "source_in_ms": start_ms, "source_out_ms": end_ms,
            "duration_ms": output_duration, "captions": len(clip_cues),
            "aspect": candidate.aspect,
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
