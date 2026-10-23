"""Burn human-approved captions into a local MP4 with FFmpeg/libass."""

import shutil
import subprocess
from pathlib import Path

from apps.api.captions import Cue, probe_media, to_srt, validate_timing
from apps.api.config import get_settings
from apps.api.ingestion import sha256_file
from apps.api.models import Asset, Transcript


def caption_output(asset_id: str, revision: int) -> Path:
    return get_settings().mediagrid_data_dir / "caption-renders" / f"{asset_id}-r{revision}.mp4"


def burn_captions(asset: Asset, transcript: Transcript, job_id: str,
                  staged_output: Path | None = None) -> dict:
    settings = get_settings()
    if not asset.media_type.startswith("video/"):
        raise ValueError("Caption video requires a video asset")
    source = settings.mediagrid_data_dir / "assets" / asset.id
    if not source.is_file() or sha256_file(source) != asset.sha256:
        raise ValueError("Caption source is missing or changed")
    if transcript.asset_id != asset.id or transcript.source_sha256 != asset.sha256:
        raise ValueError("Caption source hash differs from the approved transcript")
    if transcript.status != "APPROVED" or not transcript.cues_json:
        raise ValueError("Captions need human approval before video export")
    cues = [Cue.model_validate(item) for item in transcript.cues_json]
    duration_ms, has_audio = probe_media(source)
    validate_timing([], cues, duration_ms)
    output = caption_output(asset.id, transcript.revision)
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < source.stat().st_size + 256 * 1024 * 1024:
        raise ValueError("Not enough local disk space for caption render")
    scratch = (settings.mediagrid_data_dir / "temp" / f"captions-{job_id}").resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    subtitle = scratch / "captions.srt"
    partial = scratch / "captioned.mp4"
    try:
        subtitle.write_text(to_srt(cues), encoding="utf-8")
        ffmpeg = str(settings.mediagrid_ffmpeg_path or "ffmpeg")
        command = [
            ffmpeg, "-nostdin", "-y", "-v", "error", "-i", str(source.resolve()),
            "-vf", "subtitles=captions.srt", "-map", "0:v:0",
        ]
        if has_audio:
            command.extend(["-map", "0:a:0"])
        command.extend([
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        ])
        if has_audio:
            command.extend(["-c:a", "aac", "-b:a", "160k"])
        command.append(str(partial))
        rendered = subprocess.run(command, cwd=scratch, capture_output=True, text=True,
                                  timeout=max(300, duration_ms // 1000 * 20))
        if rendered.returncode:
            raise ValueError(f"FFmpeg caption render failed: {rendered.stderr[-1000:]}")
        rendered_duration, rendered_audio = probe_media(partial)
        if abs(rendered_duration - duration_ms) > 500 or rendered_audio != has_audio:
            raise ValueError("Caption MP4 duration or audio streams changed")
        digest = sha256_file(partial)
        partial.replace(staged_output or output)
        return {
            "output": str(output), "sha256": digest,
            "asset_id": asset.id, "source_sha256": asset.sha256,
            "transcript_revision": transcript.revision,
            "duration_ms": rendered_duration, "cues": len(cues),
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
