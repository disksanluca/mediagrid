"""Comparative evidence for M3.1. Movement measurements are not artistic scores."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from qa_creative_motion import run


def movement(video: Path) -> dict:
    raw = run("ffmpeg", "-v", "error", "-i", str(video), "-an", "-vf",
              "fps=10,scale=64:114,format=gray", "-f", "rawvideo", "-")
    size = 64*114
    frames = [raw[i:i+size] for i in range(0, len(raw), size)]
    assert len(frames) == 120
    result = {}
    for name, start, end in (("impact", 0, 20), ("reveal", 20, 50),
                             ("play", 50, 90), ("resolve", 90, 120)):
        deltas = [sum(abs(a-b) for a, b in zip(frames[i], frames[i+1], strict=True))/size
                  for i in range(start, end-1)]
        # Measures evolving composition over the act, not just adjacent-frame motion.
        separation = sum(abs(a-b) for a, b in
                         zip(frames[start+5], frames[end-2], strict=True))/size
        result[name] = {"mean_adjacent_delta": round(sum(deltas)/len(deltas), 5),
                        "min_adjacent_delta": round(min(deltas), 5),
                        "early_late_delta": round(separation, 5)}
    return result


def board(video: Path, output: Path) -> None:
    frames = [15, 36, 54, 69, 96, 141, 165, 201, 255, 279, 315, 351]
    images = output.parent / "board-frames"
    images.mkdir(exist_ok=True)
    for index, frame in enumerate(frames):
        # Static per-frame annotations avoid drawtext's mutable glyph cache when tiled.
        label = (r"drawtext=fontfile='C\:/Windows/Fonts/arial.ttf':"
                 f"text='{frame/30:06.3f} s':"
                 "x=12:y=h-30:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.7")
        run("ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf",
            f"select=eq(n\\,{frame}),scale=270:480,{label}", "-frames:v", "1",
            str(images / f"{index:02d}.jpg"))
    run("ffmpeg", "-v", "error", "-y", "-framerate", "1", "-i",
        str(images / "%02d.jpg"), "-vf", "tile=3x4", "-frames:v", "1", str(output))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    folder = args.folder.resolve()
    comparison = {"measurement": "10 Hz, 64x114 gray, absolute 8-bit pixel differences",
                  "interpretation": "Descriptive only. Not an artistic quality ranking.",
                  "human_choice": "PENDING", "versions": {}}
    for name in ("v1", "v2"):
        child = folder / name
        subprocess.run([sys.executable, str(Path(__file__).with_name("qa_creative_motion.py")),
                        str(child), "--cues", "0", "2", "5", "6.45", "7.7", "9", "10.5"],
                       check=True, capture_output=True)
        proof = json.loads((child / "proof.json").read_text(encoding="utf-8"))
        video = Path(proof["result"]["output"])
        report = json.loads((child / "qa.json").read_text(encoding="utf-8"))
        probe = json.loads((child / "ffprobe.json").read_text(encoding="utf-8"))
        v = next(s for s in probe["streams"] if s["codec_type"] == "video")
        a = next(s for s in probe["streams"] if s["codec_type"] == "audio")
        assert (v["width"], v["height"], v["nb_read_frames"]) == (1080, 1920, "360")
        assert a["channels"] == 2 and a["sample_rate"] == "48000"
        loud = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vn",
                               "-af", "ebur128=peak=true", "-f", "null", "-"],
                              check=True, capture_output=True, text=True).stderr
        (child / "loudness.txt").write_text(loud[loud.rfind("Summary:"):], encoding="utf-8")
        lufs = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", loud)[-1])
        peak = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", loud)[-1])
        assert peak < 0, "Inter-sample clipping"
        board(video, child / "frame-board.jpg")
        report.update({"integrated_lufs": lufs, "true_peak_dbfs": peak,
                       "audio_channels": a["channels"], "motion_by_act": movement(video)})
        (child / "qa.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        comparison["versions"][name] = report
    baseline = json.loads((args.baseline / "proof.json").read_text(encoding="utf-8"))
    comparison["baseline_motion_by_act"] = movement(Path(baseline["result"]["output"]))
    (folder / "comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()

