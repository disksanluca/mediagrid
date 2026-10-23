"""Render an approved original 3D story with a local Blender executable."""

import hashlib
import json
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from apps.api.captions import Cue, probe_media, to_srt
from apps.api.config import get_settings
from apps.api.ingestion import sha256_file
from apps.api.models import Asset, Narrative3D

RIG_VERSION = "migo_3d_v1"
WORLD_VERSION = "atelier_stage_v1"


def blender_script() -> Path:
    source = Path(__file__).with_name("blender_narrative.py")
    if source.is_file():
        return source
    bundled = Path(getattr(sys, "_MEIPASS", "")) / "workers" / "render" / "blender_narrative.py"
    if bundled.is_file():
        return bundled
    raise ValueError("Original 3D rig script is missing from the desktop runtime")


def blender_executable() -> Path | None:
    settings = get_settings()
    if settings.mediagrid_mode != "LOCAL":
        return None
    configured = settings.mediagrid_blender_path
    saved = settings.mediagrid_data_dir / "settings.json"
    if configured is None and saved.is_file():
        try:
            value = json.loads(saved.read_text(encoding="utf-8")).get("blender_path")
            configured = Path(value) if isinstance(value, str) and value else None
        except (OSError, ValueError):
            pass
    found = str(configured) if configured else shutil.which("blender")
    if not found:
        return None
    executable = Path(found).resolve()
    if not executable.is_file() or executable.name.lower() not in {"blender", "blender.exe"}:
        return None
    try:
        result = subprocess.run([str(executable), "--background", "--version"],
                                capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode or not result.stdout.startswith("Blender 4.5."):
        return None
    return executable


def story_payload(sequence: Narrative3D) -> dict:
    return {
        "aspect": sequence.aspect,
        "title": sequence.title,
        "shots": sequence.shots_json,
        "rig_version": sequence.rig_version,
        "world_version": sequence.world_version,
        "audio_sha256": sequence.audio_sha256,
    }


def story_sha256(sequence: Narrative3D) -> str:
    encoded = json.dumps(story_payload(sequence), ensure_ascii=False,
                         sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def narrative_output(sequence_id: str, revision: int, quality: str) -> Path:
    if quality not in {"blocking", "final"}:
        raise ValueError("Unknown 3D render quality")
    return (get_settings().mediagrid_data_dir / "narrative-renders"
            / f"{sequence_id}-r{revision}-{quality}.mp4")


def _checked(command: list[str], *, cwd: Path, timeout: int, label: str) -> None:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                            timeout=timeout, check=False)
    if result.returncode:
        raise ValueError(f"{label} failed ({result.returncode}): "
                         f"{(result.stderr or result.stdout)[-1400:]}")


def render_narrative(db: Session, sequence: Narrative3D, job_id: str, quality: str,
                     progress: Callable[[float], None] | None = None) -> dict:
    started = time.monotonic()
    blender = blender_executable()
    if blender is None:
        raise ValueError("Blender 4.5 LTS is not available on this desktop worker")
    script = blender_script()
    if sequence.rig_version != RIG_VERSION or sequence.world_version != WORLD_VERSION:
        raise ValueError("Unsupported 3D rig or world version")
    if quality == "blocking" and sequence.status != "REVIEW_REQUIRED":
        raise ValueError("Blocking preview needs a saved story awaiting review")
    if quality == "final" and sequence.status != "APPROVED":
        raise ValueError("Final 3D render needs approved blocking")
    settings = get_settings()
    ffmpeg = str(settings.mediagrid_ffmpeg_path or "ffmpeg")
    output = narrative_output(sequence.id, sequence.revision, quality)
    output.parent.mkdir(parents=True, exist_ok=True)
    scratch = (settings.mediagrid_data_dir / "temp" / f"narrative-{job_id}").resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    fps = 12 if quality == "blocking" else 24
    story = story_payload(sequence)
    total_ms = sum(shot["duration_ms"] for shot in sequence.shots_json)
    audio: Path | None = None
    if sequence.audio_asset_id:
        asset = db.get(Asset, sequence.audio_asset_id)
        if (asset is None or asset.rights_status not in {"OWNED", "LICENSED"}
                or asset.sha256 != sequence.audio_sha256):
            raise ValueError("3D audio rights or provenance changed")
        audio = settings.mediagrid_data_dir / "assets" / asset.id
        if not audio.is_file() or sha256_file(audio) != asset.sha256:
            raise ValueError("3D audio file is missing or changed")
        audio_ms, has_audio = probe_media(audio)
        if not has_audio or audio_ms + 50 < total_ms:
            raise ValueError("3D audio is shorter than the story")
    if quality == "final":
        blocking = narrative_output(sequence.id, sequence.revision, "blocking")
        if (not blocking.is_file() or not sequence.blocking_sha256
                or sha256_file(blocking) != sequence.blocking_sha256):
            raise ValueError("Approved blocking preview is missing or changed")
    if shutil.disk_usage(output.parent).free < 1024 * 1024 * 1024:
        raise ValueError("At least 1 GB of free disk is required for 3D frames")
    version = subprocess.run([str(blender), "--background", "--version"],
                             capture_output=True, text=True, timeout=15, check=True).stdout
    try:
        story_path = scratch / "story.json"
        story_path.write_text(json.dumps(story, ensure_ascii=False), encoding="utf-8")
        segments: list[Path] = []
        manifests: list[dict] = []
        for index, shot in enumerate(sequence.shots_json):
            frames_dir = scratch / f"shot-{index:02d}"
            _checked([str(blender), "--background", "--factory-startup",
                      "--python-exit-code", "21", "--python", str(script), "--",
                      "--story", str(story_path), "--shot", str(index),
                      "--quality", quality, "--output", str(frames_dir)],
                     cwd=scratch, timeout=300 if quality == "blocking" else 1200,
                     label=f"Blender shot {index + 1}")
            manifest = json.loads((frames_dir / "manifest.json").read_text(encoding="utf-8"))
            expected_frames = max(1, round(shot["duration_ms"] * fps / 1000))
            frames = sorted(frames_dir.glob("frame_*.png"))
            if (manifest.get("rig_version") != RIG_VERSION
                    or manifest.get("world_version") != WORLD_VERSION
                    or manifest.get("frames") != expected_frames
                    or manifest.get("fps") != fps or len(frames) != expected_frames):
                raise ValueError("Blender produced an incomplete or inconsistent shot")
            manifests.append(manifest)
            subtitle = scratch / f"beat-{index}.srt"
            subtitle.write_text(to_srt([Cue(start_ms=0,
                                           end_ms=shot["duration_ms"],
                                           text=shot["beat_text"])]), encoding="utf-8")
            segment = scratch / f"segment-{index:02d}.mp4"
            _checked([ffmpeg, "-nostdin", "-y", "-v", "error", "-framerate", str(fps),
                      "-start_number", "1", "-i", str(frames_dir / "frame_%04d.png"),
                      "-vf", f"subtitles={subtitle.name}", "-c:v", "libx264",
                      "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                      "-r", str(fps), str(segment)],
                     cwd=scratch, timeout=300, label=f"3D shot encode {index + 1}")
            segments.append(segment)
            if progress:
                progress(0.75 * (index + 1) / len(sequence.shots_json))
        listing = scratch / "segments.txt"
        listing.write_text("".join(f"file '{path.name}'\n" for path in segments),
                           encoding="utf-8")
        combined = scratch / "picture.mp4"
        _checked([ffmpeg, "-nostdin", "-y", "-v", "error", "-f", "concat",
                  "-safe", "1", "-i", str(listing), "-c", "copy", str(combined)],
                 cwd=scratch, timeout=300, label="3D shot concat")
        source_audio = (["-i", str(audio)] if audio else
                        ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"])
        final_temp = scratch / "with-audio.mp4"
        _checked([ffmpeg, "-nostdin", "-y", "-v", "error", "-i", str(combined),
                  *source_audio, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                  "-c:a", "aac", "-b:a", "160k", "-t", f"{total_ms / 1000:.3f}",
                  "-movflags", "+faststart", str(final_temp)],
                 cwd=scratch, timeout=300, label="3D audio mux")
        actual_ms, has_audio = probe_media(final_temp)
        if not has_audio or abs(actual_ms - total_ms) > 300:
            raise ValueError("3D final duration or audio stream is invalid")
        digest = sha256_file(final_temp)
        final_temp.replace(output)
        if progress:
            progress(0.95)
        return {
            "output": str(output), "sha256": digest, "quality": quality,
            "sequence_id": sequence.id, "revision": sequence.revision,
            "story_sha256": story_sha256(sequence), "rig_sha256": sha256_file(script),
            "rig_version": RIG_VERSION, "world_version": WORLD_VERSION,
            "shots": len(manifests), "frames": sum(item["frames"] for item in manifests),
            "fps": fps, "duration_ms": actual_ms, "aspect": sequence.aspect,
            "audio_sha256": sequence.audio_sha256,
            "audio_kind": "licensed_asset" if audio else "silence",
            "blender_version": version.splitlines()[0],
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "output_bytes": output.stat().st_size,
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
