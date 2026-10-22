"""Hash and probe local originals without loading long media into memory."""

import hashlib
import json
import subprocess
from fractions import Fraction
from pathlib import Path

from .config import get_settings


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def probe_video(path: Path) -> dict[str, int | str | None]:
    """Only accepts a local MP4 path supplied by the asset store."""
    ffprobe = get_settings().mediagrid_ffprobe_path or "ffprobe"
    try:
        result = subprocess.run(
            [str(ffprobe), "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate",
             "-of", "json", str(path.resolve())],
            check=True, capture_output=True, text=True, timeout=120,
        )
        metadata = json.loads(result.stdout)
        duration = round(float(metadata.get("format", {}).get("duration", 0)) * 1000)
    except (OSError, ValueError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as exc:
        raise ValueError("Could not probe the local MP4") from exc
    video = next(
        (stream for stream in metadata.get("streams", [])
         if stream.get("codec_type") == "video"), None,
    )
    audio = next(
        (stream for stream in metadata.get("streams", [])
         if stream.get("codec_type") == "audio"), None,
    )
    if duration <= 0 or not video or not video.get("width") or not video.get("height"):
        raise ValueError("The MP4 has no valid video stream or duration")
    try:
        fps = Fraction(video.get("r_frame_rate", "0/1"))
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("The MP4 has invalid frame rate metadata") from exc
    if fps <= 0:
        raise ValueError("The MP4 has no valid frame rate")
    return {
        "duration_ms": duration,
        "width": int(video["width"]),
        "height": int(video["height"]),
        "fps_num": fps.numerator,
        "fps_den": fps.denominator,
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name") if audio else None,
    }
