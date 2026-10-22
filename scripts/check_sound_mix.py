"""Measure an original synthetic sound mix against the voice-only proof output."""

import argparse
import math
import shutil
import subprocess
from array import array
from pathlib import Path


def rms_audio(video: Path, start: float, seconds: float) -> float:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required")
    result = subprocess.run(
        [ffmpeg, "-v", "error", "-ss", str(start), "-i", str(video),
         "-t", str(seconds), "-vn", "-ac", "1", "-ar", "16000",
         "-f", "s16le", "pipe:1"],
        check=True, capture_output=True,
    )
    samples = array("h")
    samples.frombytes(result.stdout)
    if not samples:
        raise ValueError(f"No decoded audio in {video}")
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples)) / 32768


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("mixed", type=Path)
    parser.add_argument("--start", type=float, default=29)
    parser.add_argument("--seconds", type=float, default=1)
    args = parser.parse_args()
    baseline = rms_audio(args.baseline, args.start, args.seconds)
    mixed = rms_audio(args.mixed, args.start, args.seconds)
    print(f"RMS voice-only={baseline:.6f}; mixed={mixed:.6f}")
    if mixed <= max(0.001, baseline * 5):
        raise RuntimeError("Synthetic music was not measurably present in the mixed output")


if __name__ == "__main__":
    main()
