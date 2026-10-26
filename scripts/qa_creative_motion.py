"""Measured M3 video/audio evidence. This script does not grant artistic approval."""

import argparse
import array
import hashlib
import json
import math
import subprocess
from pathlib import Path


def run(*args: str) -> bytes:
    return subprocess.run(args, check=True, capture_output=True).stdout


def audio(path: Path) -> array.array:
    samples = array.array("f")
    samples.frombytes(run("ffmpeg", "-v", "error", "-i", str(path), "-vn",
                         "-ac", "1", "-ar", "48000", "-f", "f32le", "-"))
    return samples


def envelope(samples: array.array) -> list[float]:
    return [math.sqrt(sum(s*s for s in samples[i:i+480]) / len(samples[i:i+480]))
            for i in range(0, len(samples), 480)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    folder = args.folder.resolve()
    proof = json.loads((folder / "proof.json").read_text(encoding="utf-8"))
    video = Path(proof["result"]["output"])
    source = folder / "original-score.wav"
    probe = json.loads(run("ffprobe", "-v", "error", "-count_frames", "-show_format",
                           "-show_streams", "-of", "json", str(video)))
    (folder / "ffprobe.json").write_text(json.dumps(probe, indent=2), encoding="utf-8")
    # Full video+audio decode; stderr errors cause a failure.
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"],
                             capture_output=True)
    assert decoded.returncode == 0 and not decoded.stderr.strip()
    samples = audio(video)
    reference = envelope(audio(source))
    rendered = envelope(samples)
    rms = math.sqrt(sum(s*s for s in samples) / len(samples))
    peak = max(abs(s) for s in samples)
    assert rms > .005 and peak < .99, "Audio is silent or clips"
    offsets = []
    for cue in (0, 2, 5, 9):
        start = int(cue * 100)
        a = reference[start:start+20]
        # Normalize gain; compare 200 ms envelopes at each approved scene boundary.
        def error(shift: int, start: int = start, a: list[float] = a) -> float:
            if start + shift < 0:
                return float("inf")
            b = rendered[start+shift:start+shift+len(a)]
            if len(b) != len(a):
                return float("inf")
            norm_a, norm_b = max(a), max(b)
            return sum((x/norm_a-y/norm_b)**2 for x, y in zip(a, b, strict=True))
        best = min(range(-5, 6), key=error)
        offsets.append({"cue_seconds": cue, "envelope_offset_ms": best*10,
                        "resolution_ms": 10})
    assert all(abs(item["envelope_offset_ms"]) <= 30 for item in offsets)
    black = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video),
                            "-vf", "blackdetect=d=0.03:pix_th=0.02:pic_th=0.98",
                            "-an", "-f", "null", "-"], capture_output=True, text=True, check=True)
    black_segments = [line for line in black.stderr.splitlines() if "black_start:" in line]
    assert not black_segments, black_segments
    raw = run("ffmpeg", "-v", "error", "-i", str(video), "-an", "-vf",
              "fps=10,scale=64:114,format=gray", "-f", "rawvideo", "-")
    size = 64*114
    frames = [raw[i:i+size] for i in range(0, len(raw), size)]
    deltas = [sum(abs(a-b) for a, b in zip(x, y, strict=True)) / size
              for x, y in zip(frames, frames[1:], strict=False)]
    assert len(frames) == 120 and min(deltas) > .02, "Repeated/static sampled frame"
    moments = [0, .4, 1, 1.9, 2, 2.5, 4.8, 5, 6.6, 8.8, 9, 10, 11.5, 11.967]
    frame_dir = folder / "frames"
    frame_dir.mkdir(exist_ok=True)
    for index, moment in enumerate(moments):
        target = frame_dir / f"{index:02d}-{moment:g}s.jpg"
        selected = min(359, round(moment * 30))
        run("ffmpeg", "-v", "error", "-y", "-i", str(video),
            "-frames:v", "1", "-vf", f"select=eq(n\\,{selected}),scale=360:640", str(target))
        assert target.is_file() and target.stat().st_size > 0, "Frame extraction failed"
    run("ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf",
        "fps=1/3,scale=270:480,tile=4x1", "-frames:v", "1", str(folder/"contact.jpg"))
    report = {
        "video_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
        "audio_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "full_decode": "PASS", "black_segments": black_segments,
        "black_rule": ">=98% pixels below 2% luminance for >=0.03 seconds",
        "mono_rms_dbfs": round(20*math.log10(rms), 3),
        "mono_sample_peak_dbfs": round(20*math.log10(peak), 3),
        "sync_envelopes": offsets, "sampled_frames": len(frames),
        "minimum_frame_delta_8bit": round(min(deltas), 5),
        "motion_check": "10 Hz downscaled mean absolute pixel delta; not artistic quality",
        "human_visual_and_listening_approval": "PENDING",
        "tolerances": {"video_seconds": 1/30, "container_audio_seconds": .06,
                       "audio_sync_ms": 30},
    }
    (folder / "qa.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
