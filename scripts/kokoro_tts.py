"""Fixed local Kokoro runner used by MediaGrid; it accepts text data, never code."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

SAMPLE_RATE = 24_000
ALLOWED_VOICES = {"pf_dora", "pm_alex", "pm_santa"}


def synthesize(pipeline: KPipeline, text: str, voice: str, speed: float) -> np.ndarray:
    if not text.strip() or len(text) > 8_000:
        raise ValueError("Kokoro text must contain 1..8000 characters")
    chunks = [audio for _, _, audio in pipeline(text, voice=voice, speed=speed)]
    if not chunks:
        raise RuntimeError("Kokoro returned no audio")
    return np.concatenate(chunks).astype(np.float32, copy=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text-file", type=Path)
    source.add_argument("--segments-json", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timing-output", type=Path)
    parser.add_argument("--voice", default="pm_alex", choices=sorted(ALLOWED_VOICES))
    parser.add_argument("--speed", type=float, default=1.0)
    args = parser.parse_args()
    if not 0.75 <= args.speed <= 1.35:
        parser.error("speed must be between 0.75 and 1.35")
    pipeline = KPipeline(lang_code="p", repo_id="hexgrad/Kokoro-82M")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report: dict
    if args.text_file:
        text = args.text_file.read_text(encoding="utf-8")
        audio = synthesize(pipeline, text, args.voice, args.speed)
        report = {
            "segments": [{"id": "narration", "start_ms": 0,
                          "duration_ms": round(len(audio) * 1000 / SAMPLE_RATE),
                          "text_sha256": hashlib.sha256(text.encode()).hexdigest()}],
            "duration_ms": round(len(audio) * 1000 / SAMPLE_RATE),
        }
    else:
        payload = json.loads(args.segments_json.read_text(encoding="utf-8"))
        if not isinstance(payload, list) or not 1 <= len(payload) <= 12:
            raise ValueError("segments-json must contain 1..12 segments")
        end_ms = max(int(item["start_ms"]) + int(item["slot_ms"]) for item in payload)
        if end_ms > 60_000:
            raise ValueError("Narrative audio cannot exceed 60 seconds")
        audio = np.zeros(round(end_ms * SAMPLE_RATE / 1000), dtype=np.float32)
        timings = []
        for item in payload:
            segment = synthesize(pipeline, str(item["text"]), args.voice, args.speed)
            start = round(int(item["start_ms"]) * SAMPLE_RATE / 1000)
            available = round((int(item["slot_ms"]) - 350) * SAMPLE_RATE / 1000)
            if len(segment) > available:
                raise ValueError(
                    f"Narration {item['id']} exceeds its slot by "
                    f"{round((len(segment)-available)*1000/SAMPLE_RATE)} ms"
                )
            audio[start:start + len(segment)] += segment
            timings.append({
                "id": str(item["id"]), "start_ms": int(item["start_ms"]),
                "duration_ms": round(len(segment) * 1000 / SAMPLE_RATE),
                "slot_ms": int(item["slot_ms"]),
                "text_sha256": hashlib.sha256(str(item["text"]).encode()).hexdigest(),
            })
        report = {"segments": timings, "duration_ms": end_ms}
    peak = float(np.max(np.abs(audio))) if len(audio) else 0
    if peak > 0.98:
        audio *= 0.98 / peak
    sf.write(args.output, audio, SAMPLE_RATE, subtype="PCM_16")
    report.update({
        "provider": "kokoro_local", "model": "hexgrad/Kokoro-82M",
        "voice": args.voice, "speed": args.speed, "sample_rate": SAMPLE_RATE,
        "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
    })
    if args.timing_output:
        args.timing_output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
