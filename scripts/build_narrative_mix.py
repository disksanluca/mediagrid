"""Build an original deterministic music/SFX mix around a narration WAV."""

import argparse
import hashlib
import json
import math
import random
import wave
from array import array
from pathlib import Path

RATE = 48_000


def read_voice(path: Path) -> tuple[list[float], int]:
    with wave.open(str(path), "rb") as source:
        if source.getsampwidth() != 2 or source.getnchannels() != 1:
            raise ValueError("Narration must be mono PCM16")
        rate = source.getframerate()
        raw = array("h", source.readframes(source.getnframes()))
    return [value / 32768 for value in raw], rate


def envelope(sample: int, at: int, duration: int) -> float:
    relative = sample - at
    if relative < 0 or relative >= duration:
        return 0
    edge = min(1.0, relative / max(1, RATE // 100), (duration-relative) / max(1, RATE // 80))
    return max(0.0, edge)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--narration", required=True, type=Path)
    parser.add_argument("--timings", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    timing = json.loads(args.timings.read_text(encoding="utf-8"))
    duration_ms = int(timing["duration_ms"])
    if not 45_000 <= duration_ms <= 60_000:
        raise ValueError("Narrative proof must last 45..60 seconds")
    voice, voice_rate = read_voice(args.narration)
    total = round(duration_ms * RATE / 1000)
    rng = random.Random(23051998)
    sfx = [
        (900, "message"), (7100, "whoosh"), (14_300, "tap"), (22_100, "error"),
        (29_000, "rain"), (36_000, "message"), (43_000, "tool"), (50_000, "check"),
    ]
    left, right = array("h"), array("h")
    voice_peak = music_peak = sfx_peak = 0.0
    for i in range(total):
        t = i / RATE
        voice_index = round(i * voice_rate / RATE)
        narration = voice[voice_index] if voice_index < len(voice) else 0.0
        voice_peak = max(voice_peak, abs(narration))
        chord = (math.sin(2*math.pi*110*t) + 0.55*math.sin(2*math.pi*164.81*t)
                 + 0.35*math.sin(2*math.pi*220*t))
        pulse = max(0.0, math.sin(2*math.pi*1.5*t)) ** 8
        music = 0.025*chord + 0.018*pulse*math.sin(2*math.pi*55*t)
        music *= 0.42 if abs(narration) > 0.025 else 1.0
        music_peak = max(music_peak, abs(music))
        effect_l = effect_r = 0.0
        for at_ms, kind in sfx:
            at = round(at_ms * RATE / 1000)
            if kind == "rain":
                length = round(2.2*RATE)
                env = envelope(i, at, length)
                noise = (rng.random()*2-1) if env else 0
                effect_l += noise*0.035*env
                effect_r += noise*0.028*env
                continue
            length = round((0.7 if kind == "whoosh" else 0.32)*RATE)
            env = envelope(i, at, length)
            if not env:
                continue
            rel = (i-at)/RATE
            frequency = {
                "message": 880, "whoosh": 180+900*rel, "tap": 520,
                "error": 190, "tool": 440, "check": 1040,
            }[kind]
            tone = math.sin(2*math.pi*frequency*rel)*env
            if kind == "error":
                tone += 0.5*math.sin(2*math.pi*145*rel)*env
            pan = -0.35 if kind in {"message", "tap"} else 0.35
            effect_l += tone*0.13*(1-pan)
            effect_r += tone*0.13*(1+pan)
        sfx_peak = max(sfx_peak, abs(effect_l), abs(effect_r))
        left_sample = max(-0.98, min(0.98, narration*0.88 + music*0.92 + effect_l))
        right_sample = max(-0.98, min(0.98, narration*0.88 + music*1.08 + effect_r))
        left.append(round(left_sample*32767))
        right.append(round(right_sample*32767))
    interleaved = array("h")
    for left_sample, right_sample in zip(left, right, strict=True):
        interleaved.extend((left_sample, right_sample))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(args.output), "wb") as target:
        target.setnchannels(2)
        target.setsampwidth(2)
        target.setframerate(RATE)
        target.writeframes(interleaved.tobytes())
    report = {
        "schema_version": "narrative_mix_report_v1",
        "duration_ms": duration_ms, "sample_rate": RATE, "channels": 2,
        "voice_sha256": hashlib.sha256(args.narration.read_bytes()).hexdigest(),
        "mix_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "music": "MediaGrid deterministic sine-pad v1",
        "sfx": [{"at_ms": at, "kind": kind, "origin": "procedural"} for at, kind in sfx],
        "peaks": {"voice": round(voice_peak, 6), "music": round(music_peak, 6),
                  "sfx": round(sfx_peak, 6)},
    }
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
