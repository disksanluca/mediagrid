"""Original 120 BPM procedural score. No samples, ML model or external audio."""

import array
import math
import random
import wave
from pathlib import Path

RATE = 48000
CUES = (0.0, 2.0, 5.0, 9.0)


def create_score(path: Path) -> dict:
    count = 12 * RATE
    left = array.array("f", [0]) * count
    right = array.array("f", [0]) * count
    rng = random.Random(3003)

    def tone(
        at: float, duration: float, freq: float, gain: float, pan: float, kind: str = "note"
    ) -> None:
        start = round(at * RATE)
        for i in range(min(round(duration * RATE), count - start)):
            t = i / RATE
            tail = min(1, max(0, (duration - t) / 0.07))
            attack = min(1, t / 0.004)
            if kind == "kick":
                value = math.sin(2 * math.pi * (48 * t + 5 * (1 - math.exp(-t * 30))))
                envelope = math.exp(-t * 10)
            elif kind == "air":
                value = rng.uniform(-1, 1)
                envelope = math.sin(math.pi * t / duration) ** 2 * 0.45
            elif kind == "tick":
                value = rng.uniform(-1, 1) * 0.6 + math.sin(2 * math.pi * 2700 * t) * 0.2
                envelope = math.exp(-t * 80)
            else:
                value = (
                    math.sin(2 * math.pi * freq * t)
                    + 0.25 * math.sin(2 * math.pi * freq * 2 * t)
                    + 0.12 * math.sin(2 * math.pi * freq * 3 * t)
                )
                envelope = math.exp(-t * 4)
            value *= gain * envelope * attack * tail
            left[start + i] += value * math.sqrt((1 - pan) / 2)
            right[start + i] += value * math.sqrt((1 + pan) / 2)

    for beat in range(23):
        at = beat * 0.5
        tone(at, 0.38, 55, 0.55 if at in CUES else 0.35, 0, "kick")
        if beat % 2:
            tone(at, 0.12, 1, 0.15, 0.12, "tick")
        if at >= 2:
            notes = (110, 164.8138, 146.8324, 123.4708)
            tone(at + 0.125, 0.34, notes[beat % 4], 0.13, -0.35 if beat % 2 else 0.35)
        if 5 <= at < 9:
            tone(at + 0.25, 0.07, 1, 0.16, -0.5 if beat % 2 else 0.5, "tick")
    for cue in CUES:
        tone(cue, 0.8, 55, 0.26, 0)
        tone(cue, 0.32, 1, 0.2, 0, "air")
        if cue:
            tone(cue - 0.22, 0.22, 1, 0.22, -0.35, "air")
    tone(9, 2.8, 110, 0.19, -0.3)
    tone(9, 2.8, 164.8138, 0.12, 0.3)
    pcm = array.array("h")
    peak = 0.0
    for i, (left_sample, right_sample) in enumerate(zip(left, right, strict=True)):
        fade = min(1, max(0, (12 - i / RATE) / 0.65))
        for value in (left_sample, right_sample):
            sample = math.tanh(value * 1.6) * 0.82 * fade
            peak = max(peak, abs(sample))
            pcm.append(round(sample * 32767))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as target:
        target.setparams((2, 2, RATE, count, "NONE", "not compressed"))
        target.writeframes(pcm.tobytes())
    return {
        "origin": "Original procedural synthesis",
        "seed": 3003,
        "bpm": 120,
        "cue_seconds": CUES,
        "sample_rate": RATE,
        "samples": count,
        "channels": 2,
        "peak_dbfs": round(20 * math.log10(peak), 3),
        "license": "Original MediaGrid proof; no third-party samples",
        "generator": "scripts/m3_score.py",
    }
