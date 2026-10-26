"""Original procedural media for disposable M4 proofs; never third-party samples."""

import array
import json
import math
import struct
import subprocess
import wave
import zlib
from pathlib import Path


def png(path: Path, width=640, height=640):
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            dx, dy = (x - width / 2) / (width / 2), (y - height / 2) / (height / 2)
            radius, angle = math.hypot(dx, dy), math.atan2(dy, dx)
            ribbon = (0.5 + 0.5 * math.sin(19 * radius + 4 * angle)) ** 7
            halo = math.exp(-(((radius - 0.58) / 0.22) ** 2))
            light = min(1, ribbon * halo)
            rows.extend((round(26 + 126 * light), round(20 + 214 * light), round(47 + 174 * light)))

    def chunk(name, data):
        return (
            struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))
        )

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows, 6))
        + chunk(b"IEND", b"")
    )


def score(path: Path, label: str, duration: float, version="1.1.0"):
    rate = 48000
    output = array.array("h")
    peaks, energy = 0, 0
    boundaries = {"sports": [0, 2, 5, 9], "music": [0, 4], "geo": [0, 5, 10]}[label]
    for i in range(round(duration * rate)):
        t = i / rate
        beat = t % 0.5
        note = [130.81, 164.81, 196, 246.94][int(t * 2) % 4]
        kick = math.sin(2 * math.pi * (56 * beat + 4 * (1 - math.exp(-25 * beat)))) * math.exp(
            -22 * beat
        )
        pulse = math.sin(2 * math.pi * note * t) * math.exp(-7 * beat)
        pad = (math.sin(2 * math.pi * 130.81 * t) + 0.4 * math.sin(2 * math.pi * 196 * t)) / 1.4
        # Deterministic noise, independently authored synthesis.
        noise = ((i * 1103515245 + 12345) & 0x7FFFFFFF) / 1073741824 - 1
        impact = sum(
            math.sin(2 * math.pi * 44 * (t - b)) * math.exp(-12 * (t - b))
            for b in boundaries
            if 0 <= t - b < 0.6
        )
        air = sum((1 - (b - t) / 0.28) * noise * 0.13 for b in boundaries if 0 < b - t < 0.28)
        if label == "sports":
            sample = 0.26 * kick + 0.18 * pulse + 0.08 * pad + 0.22 * impact + air
        elif label == "music":
            sample = 0.20 * kick + 0.24 * pulse + 0.11 * pad + 0.12 * impact + air * 0.5
        else:
            sample = (
                0.13 * pad + 0.06 * math.sin(2 * math.pi * 220 * t) + 0.10 * impact + 0.015 * noise
            )
        if version == "1.2.0":
            sample = directed_sample(t, label, duration)
            if label == "sports":
                # Calibrated headroom after the original score's -27.43 LUFS proof.
                sample *= 1.6
        envelope = min(1, t / 0.01, (duration - t) / 0.35)
        sample *= max(0, envelope)
        pan = 0.12 * math.sin(2 * math.pi * t / 5)
        for value in (sample * (1 - pan), sample * (1 + pan)):
            value = max(-0.92, min(0.92, value))
            peaks = max(peaks, abs(value))
            energy += value * value
            output.append(round(value * 32767))
    with wave.open(str(path), "wb") as target:
        target.setparams((2, 2, rate, len(output) // 2, "NONE", "not compressed"))
        target.writeframes(output.tobytes())
    return {
        "duration_s": duration,
        "sample_rate": rate,
        "channels": 2,
        "peak_dbfs": round(20 * math.log10(peaks), 3),
        "rms_dbfs": round(10 * math.log10(energy / len(output)), 3),
        "cues_seconds": boundaries,
        "origin": "Original deterministic MediaGrid synthesis",
        "license": "CC0-1.0 (original procedural proof material)",
        "score_version": version,
    }


def directed_sample(t, label, duration):
    """Three original, analytical scores: no model, samples, RNG state or remote media."""
    tau = math.tau
    if label == "sports":
        beat = t % 0.5
        kick = math.sin(tau * (48 * beat + 3 * (1 - math.exp(-32 * beat))))
        kick *= math.exp(-22 * beat)
        # Snare made from inharmonic sinusoids rather than broadband noise.
        snare_t = (t + 0.5) % 1
        snare = sum(math.sin(tau * f * t) for f in (713, 1187, 2143)) / 3
        snare *= math.exp(-28 * snare_t)
        bass = math.sin(tau * [55, 55, 65.406, 73.416][int(t * 2) % 4] * t)
        bass *= math.exp(-6 * beat)
        hits = sum(
            math.sin(tau * (38 * (t - b) + 2 * (1 - math.exp(-18 * (t - b)))))
            * math.exp(-9 * (t - b))
            * (1.25 if b == 9 else 1)
            for b in (0, 2, 5, 9)
            if 0 <= t - b < 1
        )
        rise = sum(
            math.sin(tau * (420 * t + 650 * (t - b + 0.3) ** 2))
            * math.sin(math.pi * (t - b + 0.3) / 0.3) ** 2
            for b in (2, 5, 9)
            if 0 < b - t < 0.3
        )
        release = min(1, max(0, (duration - t) / 0.7))
        return (0.25 * kick + 0.13 * snare + 0.12 * bass + 0.28 * hits + 0.07 * rise) * release
    if label == "music":
        # Original Cmaj7 -> Am7 voicing, quarter-note arpeggio and resolved final chord.
        chord = (130.813, 164.814, 195.998, 246.942) if t < 4 else (110, 130.813, 164.814, 195.998)
        pulse_t = t % 0.625
        note = chord[int(t / 0.625) % 4] * 2
        bell = (math.sin(tau * note * t) + 0.22 * math.sin(tau * note * 2.01 * t)) * math.exp(
            -4 * pulse_t
        )
        pad = sum(math.sin(tau * f * t + 0.12 * math.sin(t * 0.7)) for f in chord) / 4
        final = sum(math.sin(tau * f * t) for f in (130.813, 195.998, 261.626)) / 3
        final *= math.exp(-1.8 * max(0, t - 8.75)) if t >= 8.75 else 0
        return (0.17 * pad + 0.23 * bell + 0.16 * final) * min(1, (duration - t) / 0.8)
    # Geo: slow harmonic bed, three location bells, filtered wind-like interference.
    bed = (
        math.sin(tau * 98 * t) + 0.5 * math.sin(tau * 146.832 * t) + 0.3 * math.sin(tau * 196 * t)
    ) / 1.8
    breath = (
        (0.55 + 0.45 * math.sin(t * 0.7))
        * (math.sin(tau * 293.665 * t) + math.sin(tau * 294.1 * t))
        / 2
    )
    bell = sum(
        (math.sin(tau * freq * (t - b)) + 0.25 * math.sin(tau * freq * 2.01 * (t - b)))
        * math.exp(-2.5 * (t - b))
        for b, freq in ((0, 392), (5, 493.883), (10, 587.33))
        if 0 <= t - b < 3
    )
    return (0.19 * bed + 0.055 * breath + 0.21 * bell) * min(1, (duration - t) / 1.1)


def create_media(folder: Path, label: str, duration: float, ffmpeg="ffmpeg", version="1.1.0"):
    folder.mkdir(parents=True, exist_ok=True)
    soundtrack = folder / "score.wav"
    provenance = score(soundtrack, label, duration, version)
    files = {"score": (soundtrack, "audio/wav")}
    if label == "music":
        cover = folder / "orbita-original.png"
        png(cover)
        waveform = folder / "original-waveform.mp4"
        subprocess.run(
            [
                str(ffmpeg),
                "-y",
                "-v",
                "error",
                "-i",
                str(soundtrack),
                "-filter_complex",
                "[0:a]aformat=channel_layouts=mono,showwaves=s=1080x160:mode=cline:rate=30:colors=0x98EADA[v]",
                "-map",
                "[v]",
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-r",
                "30",
                "-t",
                str(duration),
                str(waveform),
            ],
            check=True,
            timeout=120,
        )
        files.update(cover=(cover, "image/png"), waveform=(waveform, "video/mp4"))
    (folder / "media-provenance.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )
    return files
