"""M3.2 broadcast score: original instruments and explicit cues, no sampled media."""

import array
import hashlib
import math
import random
import re
import subprocess
import wave
from pathlib import Path

RATE = 48000
SEED = 3202
CUES = (0, 2, 5, 6.45, 7.7, 9, 10.5)


def create_score(path: Path) -> dict:
    count = 12 * RATE
    channels = [array.array("d", [0]) * count for _ in range(2)]
    rng = random.Random(SEED)
    events = []

    def event(at, duration, kind, gain, frequency=110, pan=0, pan_end=None, role="accent"):
        events.append({"at_seconds": at, "duration": duration, "instrument": kind,
                       "gain": gain, "frequency": frequency, "pan": pan,
                       "pan_end": pan if pan_end is None else pan_end, "role": role})
        start = round(at * RATE)
        low = previous = 0.
        for j in range(min(round(duration*RATE), count-start)):
            t, u = j/RATE, j/RATE/duration
            noise = rng.uniform(-1, 1)
            low = .88*low+.12*noise
            high = noise-previous
            previous = noise
            attack = min(1, t/.005)
            release = min(1, (duration-t)/.055)
            if kind == "sub":
                # Opening: descending body rather than a flat repeated drum.
                signal = math.sin(2*math.pi*(44*t+5*(1-math.exp(-t*25))))*math.exp(-t*8)
            elif kind == "glass":
                # Reveal: an original inharmonic struck resonator.
                signal = sum(math.sin(2*math.pi*frequency*r*t)*math.exp(-t*d)*g
                             for r, d, g in ((1, 5, .6), (2.71, 12, .2), (4.13, 20, .1)))
            elif kind == "wood":
                # Field/contact: short lower-mid percussion, not the opening sub.
                signal = (.65*math.sin(2*math.pi*frequency*t)+low)*math.exp(-t*24)
                signal += .1*high*math.exp(-t*110)
            elif kind == "air":
                signal = low*math.sin(math.pi*u)**2*2.7
            elif kind == "reverse":
                signal = (low+.13*math.sin(2*math.pi*(170*t+280*t*t)))
                signal *= math.sin(math.pi*u/2)**3
            elif kind == "brush":
                signal = (low*.7+high*.12)*math.exp(-t*45)
            elif kind == "resolve":
                # Climax: tonal body opens into a held consonant interval.
                signal = sum(g*math.sin(2*math.pi*frequency*r*t)
                             for r, g in ((1, .6), (1.5, .25), (2, .15)))
                signal *= math.exp(-t*1.6)
            else:
                raise ValueError(f"Unsupported instrument: {kind}")
            moving_pan = pan if pan_end is None else pan+(pan_end-pan)*u
            signal *= gain*attack*release
            for c, side in enumerate((-1, 1)):
                sample = signal*math.sqrt((1+side*moving_pan)/2)
                channels[c][start+j] += sample
                if kind in ("glass", "wood", "resolve"):
                    for delay, level in ((.071, .13), (.143, .065)):
                        dest = start+j+round(delay*RATE)
                        if dest < count:
                            channels[1-c][dest] += sample*level

    event(0, .75, "sub", .62, role="opening body")
    event(.025, .2, "brush", .15, pan=-.15, role="opening edge")
    for at in (.5, 1):
        event(at, .2, "wood", .12, 155, -.2, role="opening cadence")
    event(1.52, .48, "reverse", .22, pan=-.5, pan_end=.4, role="reveal anticipation")
    event(2, .9, "glass", .4, 330, .35, role="reveal identity")
    event(2, .45, "sub", .23, role="reveal weight")
    event(2.18, 1.55, "air", .13, pan=.6, pan_end=-.55, role="orbital pass")
    event(3.2, .7, "glass", .16, 495, -.4, role="orbital reflection")
    event(4.48, .52, "reverse", .24, pan=.2, pan_end=-.6, role="field anticipation")
    event(5, .35, "wood", .49, 145, -.5, role="field identity")
    event(5, .5, "sub", .27, role="field weight")
    for i, at in enumerate((5.5, 6, 6.75, 7.25, 8)):
        event(at, .15, "brush", .12 if i % 2 else .17, pan=(-1)**i*.5,
              role="syncopated subdivision")
        if i in (1, 3):
            event(at+.125, .12, "wood", .075, 250, (-1)**(i+1)*.3, role="ghost note")
    # Panning follows screen-space ball travel from left through center to right.
    event(5.8, .65, "air", .18, pan=-.55, pan_end=0, role="first ball travel")
    event(6.45, .28, "wood", .38, 185, 0, role="center contact")
    event(7.05, .65, "air", .22, pan=0, pan_end=.6, role="second ball travel")
    event(7.7, .3, "wood", .4, 225, .6, role="right contact")
    event(8.32, .68, "reverse", .25, pan=.55, pan_end=0, role="climax anticipation")
    event(9, .7, "sub", .48, role="climax body")
    event(9, 2.95, "resolve", .4, 110, -.15, role="harmonic resolution")
    event(9.02, .7, "glass", .18, 660, .4, role="climax highlight")
    event(9.65, .85, "air", .08, pan=0, pan_end=.5, role="settling travel")
    event(10.5, .85, "glass", .12, 440, .45, role="settling accent")

    def write(gain):
        pcm = array.array("h")
        for i in range(count):
            fade = min(1, (12-i/RATE)/.5)
            for channel in channels:
                value = channel[i]*gain*fade
                if abs(value) >= 1:
                    raise ValueError("Source audio would clip")
                pcm.append(round(value*32767))
        with wave.open(str(path), "wb") as target:
            target.setparams((2, 2, RATE, count, "NONE", "not compressed"))
            target.writeframes(pcm.tobytes())

    peak = max(max(abs(v) for v in channel) for channel in channels)
    initial = .68/peak
    write(initial)
    measured = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128=peak=true",
         "-f", "null", "-"], check=True, capture_output=True, text=True,
    ).stderr
    source_lufs = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", measured)[-1])
    # Compensates only the existing 0.9 mixer gain: target final around -22.5 LUFS.
    # A fixed scalar preserves hierarchy. Peak ceiling takes precedence.
    gain = initial*min(10**((-21.6-source_lufs)/20), 1)
    write(gain)
    return {
        "variant": "broadcast_final", "seed": SEED, "sample_rate": RATE,
        "channels": 2, "samples_per_channel": count,
        "origin": "Original procedural oscillators/resonators/filtered noise; no samples",
        "license": "Original MediaGrid procedural sound design; project use permitted",
        "generator": "scripts/m3_2_score.py",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "linear_gain": gain, "peak_ceiling": .68, "target_source_lufs": -21.6,
        "measured_initial_source_lufs": source_lufs,
        "normalization": "Single fixed scalar, never above initial peak ceiling; no limiter",
        "cues": CUES, "events": events, "human_listening_approval": "PENDING",
    }
