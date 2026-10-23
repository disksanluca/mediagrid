"""Create a small local proxy and waveform from an immutable imported MP4."""

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from apps.api.config import get_settings
from apps.api.ingestion import probe_video, sha256_file
from apps.api.models import Asset, Job


@dataclass(frozen=True)
class ProxyBuild:
    result: dict
    metadata: dict
    staged_proxy: Path
    final_proxy: Path
    staged_waveform: Path | None
    final_waveform: Path


def build_proxy(db: Session, job: Job, asset: Asset) -> ProxyBuild:
    settings = get_settings()
    source = settings.mediagrid_data_dir / "assets" / asset.id
    if not source.is_file() or asset.media_type != "video/mp4":
        raise ValueError("Proxy source MP4 is unavailable")
    if sha256_file(source) != asset.sha256 or job.payload.get("sha256") != asset.sha256:
        raise ValueError("Original changed after import; proxy was not created")
    info = probe_video(source)
    duration_ms = int(info["duration_ms"])
    folder = settings.mediagrid_data_dir / "proxies"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{asset.id}.mp4"
    attempt_id = f"{job.id}.{uuid4().hex}"
    temporary = folder / f".{asset.id}.{attempt_id}.mp4"
    waveform = folder / f"{asset.id}-waveform.png"
    ffmpeg = str(settings.mediagrid_ffmpeg_path or "ffmpeg")
    job.progress = 0.05
    db.commit()
    command = [
        ffmpeg, "-nostdin", "-y", "-v", "error",
        "-progress", "pipe:1", "-i", str(source),
        "-map", "0:v:0", "-map", "0:a:0?",
        "-vf", "scale=640:-2:flags=fast_bilinear", "-r", "12",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart",
        str(temporary),
    ]
    last_commit = time.monotonic()
    progress_seconds = 0.0
    wave_temp: Path | None = None
    waveform_status = "NO_AUDIO"
    try:
        with subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
        ) as process:
            assert process.stdout is not None
            for line in process.stdout:
                if line.startswith(("out_time_us=", "out_time_ms=")):
                    try:
                        progress_seconds = int(line.partition("=")[2]) / 1_000_000
                    except ValueError:
                        continue
                if line.startswith("progress=") and time.monotonic() - last_commit >= 1:
                    job.progress = min(0.87, 0.05 + 0.82 * progress_seconds * 1000 / duration_ms)
                    db.commit()
                    last_commit = time.monotonic()
            stderr = process.stderr.read() if process.stderr else ""
            if process.wait() != 0:
                raise ValueError(f"FFmpeg proxy failed: {stderr[-1000:]}")
        proxy_info = probe_video(temporary)
        if abs(int(proxy_info["duration_ms"]) - duration_ms) > max(1000, duration_ms // 100):
            raise ValueError("Proxy duration differs from its original")
        proxy_hash = sha256_file(temporary)
        job.progress = 0.9
        db.commit()
        waveform_hash = None
        if info["audio_codec"]:
            wave_temp = folder / f".{asset.id}.{attempt_id}-waveform.png"
            wave_cmd = [
                ffmpeg, "-nostdin", "-y", "-v", "error", "-i", str(source),
                "-filter_complex",
                "[0:a:0]aformat=channel_layouts=mono,"
                "showwavespic=s=1200x160:colors=0xDCF769[out]",
                "-map", "[out]", "-frames:v", "1", str(wave_temp),
            ]
            try:
                subprocess.run(wave_cmd, check=True, capture_output=True, timeout=7200)
                waveform_hash = sha256_file(wave_temp)
                waveform_status = "READY"
            except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                waveform_status = "FAILED"
        metadata = {
            **(asset.metadata_json or {}),
            "proxy_sha256": proxy_hash,
            "proxy_size_bytes": temporary.stat().st_size,
            "proxy_duration_ms": int(proxy_info["duration_ms"]),
            "waveform_sha256": waveform_hash,
            "waveform_status": waveform_status,
            "ingest_status": "READY" if waveform_status != "FAILED" else "WAVEFORM_FAILED",
        }
        result = {
            "asset_id": asset.id, "source_sha256": asset.sha256,
            "proxy_sha256": proxy_hash, "proxy_duration_ms": int(proxy_info["duration_ms"]),
            "proxy_size_bytes": temporary.stat().st_size,
            "waveform_sha256": waveform_hash, "waveform_status": waveform_status,
        }
        return ProxyBuild(
            result, metadata, temporary, target,
            wave_temp if waveform_status == "READY" else None, waveform,
        )
    except Exception:
        temporary.unlink(missing_ok=True)
        if wave_temp is not None:
            wave_temp.unlink(missing_ok=True)
        raise
    finally:
        if wave_temp is not None and waveform_status != "READY":
            wave_temp.unlink(missing_ok=True)
