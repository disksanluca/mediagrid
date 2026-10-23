"""Offline word timing from an explicitly configured local model directory."""

import importlib.metadata
import importlib.util
import subprocess
from collections.abc import Callable
from pathlib import Path

from .captions import Word, probe_media
from .config import get_settings

CHUNK_MS = 5 * 60 * 1000


def available() -> bool:
    model = get_settings().mediagrid_asr_model_dir
    return bool(
        model and model.is_dir() and (model / "model.bin").is_file()
        and (model / "config.json").is_file()
        and (model / "tokenizer.json").is_file()
        and (model / "vocabulary.txt").is_file()
        and importlib.util.find_spec("faster_whisper")
    )


def transcribe_words(
    path: Path, on_chunk: Callable[[float], None] | None = None,
) -> tuple[list[Word], str, str]:
    """No model identifier can trigger a download; only a local path is accepted."""
    if not available():
        raise RuntimeError("Configure MEDIAGRID_ASR_MODEL_DIR and install the asr extra")
    import numpy as np
    from faster_whisper import WhisperModel

    settings = get_settings()
    duration_ms, has_audio = probe_media(path)
    if not has_audio:
        raise ValueError("Media has no audio stream")
    model_dir = settings.mediagrid_asr_model_dir
    assert model_dir is not None
    model = WhisperModel(str(model_dir.resolve()), device="cpu", compute_type="int8", cpu_threads=8)
    ffmpeg = str(settings.mediagrid_ffmpeg_path or "ffmpeg")
    words: list[Word] = []
    language: str | None = None
    for start_ms in range(0, duration_ms, CHUNK_MS):
        length_ms = min(CHUNK_MS, duration_ms - start_ms)
        decoded = subprocess.run([
            ffmpeg, "-nostdin", "-v", "error", "-i", str(path.resolve()),
            "-ss", f"{start_ms / 1000:.3f}", "-t", f"{length_ms / 1000:.3f}",
            "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-",
        ], capture_output=True, check=True, timeout=max(120, length_ms // 1000 * 3))
        waveform = np.frombuffer(decoded.stdout, dtype="<f4")
        if waveform.size == 0:
            raise ValueError(f"Empty audio block at {start_ms} ms")
        segments, info = model.transcribe(
            waveform, language=language, beam_size=3, vad_filter=True,
            word_timestamps=True, condition_on_previous_text=False,
        )
        language = info.language
        for segment in segments:
            if segment.words is None:
                raise ValueError("ASR returned a segment without word timestamps")
            for word in segment.words:
                text = word.word.strip()
                if not text:
                    continue
                start = start_ms + round(word.start * 1000)
                end = max(start + 1, start_ms + round(word.end * 1000))
                words.append(Word(
                    start_ms=start, end_ms=min(duration_ms, end),
                    text=text, confidence=word.probability,
                ))
        if on_chunk:
            on_chunk(min(1.0, (start_ms + length_ms) / duration_ms))
    return words, language or "und", importlib.metadata.version("faster-whisper")
