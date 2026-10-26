"""Original stereo sound design: deterministic synthesis, no recordings or paid services."""

import array
import hashlib
import math
import random
import wave
from pathlib import Path

RATE = 48000
VARIANTS = ("editorial", "broadcast")


def create_score(path: Path, variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError("Unknown art direction")
    energetic = variant == "broadcast"
    rng = random.Random(3102 if energetic else 3101)
    count = RATE * 12
    channels = [array.array("d", [0]) * count for _ in range(2)]
    events = []

    def event(at, length, kind, gain, frequency=110, pan=0, role="gesture"):
        events.append({"at_seconds": at, "duration": length, "kind": kind, "role": role,
                       "gain": gain, "frequency": frequency, "pan": pan})
        start = round(at * RATE)
        low = 0.
        for j in range(min(round(length * RATE), count - start)):
            t = j / RATE
            u = t / length
            attack = min(1, t / .006)
            release = min(1, (length - t) / .05)
            low = .86 * low + .14 * rng.uniform(-1, 1)
            if kind == "impact":
                value = math.sin(2 * math.pi * (45*t + 4*(1-math.exp(-t*32))))
                value = value * math.exp(-t*7) + low * math.exp(-t*45)*.5
            elif kind == "air":
                # Band-limited turbulence travels in stereo before a visual impact.
                value = low * math.sin(math.pi*u)**2 * 2.2
            elif kind == "snap":
                value = (low*2 + math.sin(2*math.pi*frequency*t)*.3)*math.exp(-t*60)
            elif kind == "riser":
                value = (low*1.3 + .2*math.sin(2*math.pi*(130*t+260*t*t)))
                value *= math.sin(math.pi*u/2)**3
            elif kind == "pad":
                value = (math.sin(2*math.pi*frequency*t)
                         + .22*math.sin(2*math.pi*(frequency*1.503)*t))
                value *= math.sin(math.pi*u)**.8 * .45
            else:
                value = (math.sin(2*math.pi*frequency*t)
                         + .3*math.sin(2*math.pi*frequency*2*t))
                value *= math.exp(-t*(6 if energetic else 3.6))
            value *= gain * attack * release
            moving_pan = max(-.9, min(.9, pan + (u-.5)*.7 if kind == "air" else pan))
            for c, side in enumerate((-1, 1)):
                sample = value * math.sqrt((1+side*moving_pan)/2)
                channels[c][start+j] += sample
                # Two quiet reflections supply depth without washing out the transients.
                if kind in ("note", "snap", "impact"):
                    for delay, level in ((.083, .12), (.173, .07)):
                        dest = start+j+round(delay*RATE)
                        if dest < count:
                            channels[1-c][dest] += sample*level

    # Four approved macro cues; rhythmic space is deliberately different by variant.
    for at, gain in ((0, .6), (2, .48), (5, .56), (9, .72)):
        event(at, .8, "impact", gain, role="act boundary")
        if at:
            event(at-(.24 if energetic else .5), .24 if energetic else .5,
                  "riser", .24 if energetic else .16, role="anticipation")
            event(at, .4, "air", .15, pan=.3, role="transition release")
    event(.2, 4.3, "pad", .12, 55, -.3, "low atmosphere")
    event(2.08, 2.7, "pad", .16, 164.8138, .3, "reveal depth")
    for at, note in ((2.25, 110), (3, 164.8138), (3.75, 146.8324)):
        event(at, .65, "note", .13, note, -.35 if at < 3 else .35, "orbit motif")
    for at, pan in ((6.45, -.25), (7.7, .35)):
        event(at, .45, "impact", .36, pan=pan, role="ball contact")
        event(at-.17, .25, "air", .18, pan=pan, role="trajectory")
    for i, at in enumerate((5.5, 6, 6.75, 7.25, 8, 8.5)):
        event(at, .16, "snap", .12 if energetic else .065, 1900, (-1)**i*.45,
              "subdivision")
        if energetic:
            event(at+.125, .11, "snap", .075, 2400, (-1)**(i+1)*.6, "ghost accent")
            event(at, .4, "note", .1, (82.4069, 110, 146.8324)[i % 3], 0, "drive")
    event(8.4, .6, "riser", .19, role="climax anticipation")
    for freq, pan in ((55, 0), (110, -.3), (164.8138, .3)):
        event(9.02, 2.8, "pad", .23, freq, pan, "harmonic resolution")
    event(9, 1.7, "note", .24, 55, 0, "climax body")
    event(10.5, .5, "note", .11, 220, .3, "settling accent")
    if energetic:
        for at in (.5, 1, 1.5, 2.5, 3.5, 5.5, 7, 8):
            event(at, .35, "impact", .18, role="broadcast pulse")
    peak = max(max(abs(v) for v in c) for c in channels)
    # Identical ceiling, not a louder V2. No limiter or loudness maximizer.
    normalization = .68 / peak
    pcm = array.array("h")
    energy = 0.
    for i in range(count):
        fade = min(1, (12-i/RATE)/.48)
        for c in channels:
            value = c[i]*normalization*fade
            energy += value*value
            pcm.append(round(value*32767))
    with wave.open(str(path), "wb") as target:
        target.setparams((2, 2, RATE, count, "NONE", "not compressed"))
        target.writeframes(pcm.tobytes())
    return {"variant": variant, "seed": 3102 if energetic else 3101,
            "origin": "Original additive/noise synthesis; no samples or external assets",
            "license": "Original MediaGrid procedural sound design; project use permitted",
            "generator": "scripts/m3_1_score.py",
            "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "sample_rate": RATE, "samples_per_channel": count, "channels": 2,
            "peak_ceiling_dbfs": 20*math.log10(.68),
            "rms_dbfs": 20*math.log10(math.sqrt(energy/(2*count))),
            "events": events, "human_listening_approval": "PENDING"}

