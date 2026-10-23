"""Validate and normalize an owned narration before it enters the render pipeline."""

import hashlib
import json
import subprocess
from pathlib import Path

from fastapi import HTTPException, UploadFile

from .config import get_settings

MAX_RECORDING_BYTES = 50 * 1024 * 1024
MAX_RECORDING_SECONDS = 300


def _duration(path: Path, *, allow_unknown: bool = False) -> float | None:
    executable = str(get_settings().mediagrid_ffprobe_path or "ffprobe")
    try:
        result = subprocess.run(
            [executable, "-v", "error", "-select_streams", "a:0", "-show_entries",
             "stream=codec_type:format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, check=True, timeout=30,
        )
        info = json.loads(result.stdout)
        if not info.get("streams"):
            raise ValueError("No audio stream")
        value = info.get("format", {}).get("duration")
        if value in {None, "N/A"} and allow_unknown:
            # MediaRecorder often writes WebM without a seekable duration header.
            # The bounded PCM conversion below supplies an exact duration.
            return None
        duration = float(value)
        if not 0.2 <= duration <= MAX_RECORDING_SECONDS:
            raise ValueError("Audio duration outside accepted range")
        return duration
    except FileNotFoundError as exc:
        raise HTTPException(503, "FFprobe local indisponível") from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(422, "Tempo esgotado ao verificar a narração") from exc
    except (subprocess.CalledProcessError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, "Arquivo sem áudio válido de até 5 minutos") from exc


def normalize_recording(file: UploadFile, source: Path, output: Path) -> dict:
    """Read a bounded upload and return hashes/duration of a verified PCM WAV."""
    size = 0
    original_hash = hashlib.sha256()
    with source.open("wb") as destination:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_RECORDING_BYTES:
                raise HTTPException(413, "Narração acima do limite de 50 MB")
            original_hash.update(chunk)
            destination.write(chunk)
    if not size:
        raise HTTPException(422, "Arquivo de narração vazio")
    _duration(source, allow_unknown=True)
    executable = str(get_settings().mediagrid_ffmpeg_path or "ffmpeg")
    try:
        subprocess.run(
            [executable, "-nostdin", "-v", "error", "-y", "-i", str(source),
             "-map", "0:a:0", "-vn", "-t", str(MAX_RECORDING_SECONDS + 1),
             "-ac", "1", "-ar", "48000",
             "-c:a", "pcm_s16le", str(output)],
            capture_output=True, text=True, check=True, timeout=90,
        )
    except FileNotFoundError as exc:
        raise HTTPException(503, "FFmpeg local indisponível") from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(422, "Não foi possível converter esta narração") from exc
    duration = _duration(output)
    if duration is None:
        raise HTTPException(422, "Não foi possível medir a narração convertida")
    if not output.is_file() or output.stat().st_size == 0:
        raise HTTPException(422, "Narração convertida vazia")
    return {
        "original_sha256": original_hash.hexdigest(),
        "wav_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "size_bytes": size,
        "duration_seconds": duration,
    }
