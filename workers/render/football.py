"""Render only an approved, human-marked sequence from hashed local media."""

import shutil
import subprocess
from pathlib import Path

from sqlalchemy.orm import Session

from apps.api.captions import Cue, probe_media, to_srt
from apps.api.config import get_settings
from apps.api.ingestion import sha256_file
from apps.api.models import Asset, FootballSequence
from workers.render.clips import video_size


def football_output(sequence_id: str, revision: int) -> Path:
    return (get_settings().mediagrid_data_dir / "football-renders"
            / f"{sequence_id}-r{revision}.mp4")


def picture_filter(source: Path, aspect: str, focus_x: float, focus_y: float) -> str:
    width, height = video_size(source)
    target_w, target_h = (1080, 1920) if aspect == "vertical" else (1920, 1080)
    if width * target_h >= height * target_w:
        crop_h = height // 2 * 2
        crop_w = int(crop_h * target_w / target_h) // 2 * 2
    else:
        crop_w = width // 2 * 2
        crop_h = int(crop_w * target_h / target_w) // 2 * 2
    if min(crop_w, crop_h) < 2 or target_w / crop_w > 3 or target_h / crop_h > 3:
        raise ValueError("Football source resolution is too low for this crop")
    x = int((width - crop_w) * focus_x) // 2 * 2
    y = int((height - crop_h) * focus_y) // 2 * 2
    return (f"crop={crop_w}:{crop_h}:{x}:{y},"
            f"scale={target_w}:{target_h}:flags=lanczos,fps=30")


def render_football(db: Session, sequence: FootballSequence, job_id: str) -> dict:
    if sequence.status != "APPROVED" or not sequence.shots_json:
        raise ValueError("Current football sequence needs human approval")
    settings = get_settings()
    output = football_output(sequence.id, sequence.revision)
    output.parent.mkdir(parents=True, exist_ok=True)
    scratch = (settings.mediagrid_data_dir / "temp" / f"football-{job_id}").resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    ffmpeg = str(settings.mediagrid_ffmpeg_path or "ffmpeg")
    expected_ms = 0
    source_hashes: dict[str, str] = {}
    try:
        segment_paths: list[Path] = []
        for index, shot in enumerate(sequence.shots_json):
            asset = db.get(Asset, shot["asset_id"])
            if asset is None or asset.rights_status not in {"OWNED", "LICENSED"}:
                raise ValueError("Football source or rights changed")
            source = settings.mediagrid_data_dir / "assets" / asset.id
            if not source.is_file() or sha256_file(source) != shot["source_sha256"]:
                raise ValueError("Football source hash changed")
            if shot["source_sha256"] != asset.sha256:
                raise ValueError("Football asset provenance changed")
            duration_ms, has_audio = probe_media(source)
            in_ms, out_ms = shot["in_ms"], shot["out_ms"]
            if not 0 <= in_ms < out_ms <= duration_ms + 50:
                raise ValueError("Football shot range exceeds original")
            if shot["role"] in {"action", "replay"} and not shot.get("verified_event_id"):
                raise ValueError("Action or replay lost verified event ID")
            segment_ms = out_ms - in_ms
            expected_ms += segment_ms
            source_hashes[asset.id] = asset.sha256
            filters = [picture_filter(source, sequence.aspect,
                                      shot["focus_x"], shot["focus_y"])]
            label = " · ".join(part for part in (
                sequence.score_label, "REPLAY" if shot["role"] == "replay" else None
            ) if part)
            if label:
                subtitle = scratch / f"label-{index}.srt"
                subtitle.write_text(to_srt([Cue(
                    start_ms=0, end_ms=segment_ms, text=label
                )]), encoding="utf-8")
                filters.append(f"subtitles={subtitle.name}")
            segment = scratch / f"shot-{index:02d}.mp4"
            command = [ffmpeg, "-nostdin", "-y", "-v", "error",
                       "-ss", f"{in_ms / 1000:.3f}", "-i", str(source.resolve())]
            if not has_audio:
                command += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            command += [
                "-t", f"{segment_ms / 1000:.3f}", "-vf", ",".join(filters),
                "-map", "0:v:0", "-map", "0:a:0" if has_audio else "1:a:0",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                "-ar", "48000", "-ac", "2", "-movflags", "+faststart",
                str(segment),
            ]
            result = subprocess.run(command, cwd=scratch, capture_output=True,
                                    text=True, timeout=max(300, segment_ms // 50))
            if result.returncode:
                raise ValueError(f"Football shot render failed: {result.stderr[-1000:]}")
            segment_paths.append(segment)
        required_bytes = sum(p.stat().st_size for p in segment_paths) + 256 * 1024 * 1024
        if shutil.disk_usage(output.parent).free < required_bytes:
            raise ValueError("Not enough local disk space for football render")
        concat = scratch / "shots.txt"
        concat.write_text("".join(
            f"file '{path.name}'\n" for path in segment_paths
        ), encoding="utf-8")
        combined = scratch / "combined.mp4"
        result = subprocess.run([
            ffmpeg, "-nostdin", "-y", "-v", "error", "-f", "concat", "-safe", "1",
            "-i", str(concat), "-c", "copy", "-movflags", "+faststart", str(combined),
        ], cwd=scratch, capture_output=True, text=True, timeout=300)
        if result.returncode:
            raise ValueError(f"Football concat failed: {result.stderr[-1000:]}")
        actual_ms, has_audio = probe_media(combined)
        if not has_audio or abs(actual_ms - expected_ms) > max(750, len(segment_paths) * 150):
            raise ValueError("Football MP4 lost audio or has invalid duration")
        digest = sha256_file(combined)
        combined.replace(output)
        return {
            "output": str(output), "sha256": digest,
            "sequence_id": sequence.id, "revision": sequence.revision,
            "duration_ms": actual_ms, "shots": len(segment_paths),
            "source_sha256": source_hashes, "aspect": sequence.aspect,
            "score_source_url": sequence.score_source_url,
            "replay_count": sum(s["role"] == "replay" for s in sequence.shots_json),
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
