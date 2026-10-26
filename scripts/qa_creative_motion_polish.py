"""M3.2 QA against the preserved M3.1 V2. No artistic approval is inferred."""

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

from qa_creative_motion import run
from qa_creative_motion_refinement import board, movement


def loudness(path: Path) -> tuple[float, float, str]:
    log = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-vn", "-af", "ebur128=peak=true",
         "-f", "null", "-"], check=True, capture_output=True, text=True,
    ).stderr
    return (float(re.findall(r"I:\s+(-?[\d.]+) LUFS", log)[-1]),
            float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", log)[-1]),
            "\n".join(line.rstrip() for line in log[log.rfind("Summary:"):].splitlines())+"\n")


def field_luma(path: Path) -> dict:
    values = run("ffmpeg", "-v", "error", "-ss", "6.7", "-i", str(path),
                 "-frames:v", "1", "-vf",
                 "scale=1080:1920,crop=720:750:180:800,scale=72:75,format=gray",
                 "-f", "rawvideo", "-")
    mean = sum(values)/len(values)
    return {"mean_8bit": round(mean, 3),
            "stddev_8bit": round(math.sqrt(sum((v-mean)**2 for v in values)/len(values)), 3),
            "region": "x180 y800 w720 h750 at 6.7s; includes ball/route, not a contrast rating"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path, help="M3.2 version folder containing proof.json")
    parser.add_argument("--baseline", type=Path, required=True, help="M3.1 V2 folder")
    args = parser.parse_args()
    folder = args.folder.resolve()
    old = json.loads((args.baseline / "proof.json").read_text(encoding="utf-8"))
    proof = json.loads((folder / "proof.json").read_text(encoding="utf-8"))
    video, before = Path(proof["result"]["output"]), Path(old["result"]["output"])
    assert hashlib.sha256(before.read_bytes()).hexdigest() == old["result"]["sha256"]
    subprocess.run([sys.executable, str(Path(__file__).with_name("qa_creative_motion.py")),
                    str(folder), "--cues", "0", "2", "5", "6.45", "7.7", "9", "10.5"],
                   check=True, capture_output=True)
    qa = json.loads((folder / "qa.json").read_text(encoding="utf-8"))
    probe = json.loads((folder / "ffprobe.json").read_text(encoding="utf-8"))
    v = next(s for s in probe["streams"] if s["codec_type"] == "video")
    a = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    assert (v["width"], v["height"], v["nb_read_frames"]) == (1080, 1920, "360")
    assert a["channels"] == 2 and a["sample_rate"] == "48000"
    lufs, peak, log = loudness(video)
    old_lufs, old_peak, _ = loudness(before)
    assert peak < -1, "Less than 1 dB true-peak headroom"
    assert lufs <= old_lufs+.5, "Refinement must not rely on increased integrated loudness"
    (folder / "loudness.txt").write_text(log, encoding="utf-8")
    board(video, folder / "frame-board.jpg")
    # Do not write into the baseline proof.
    board(before, folder / "before-board.jpg")
    run("ffmpeg", "-v", "error", "-y", "-i", str(folder/"before-board.jpg"),
        "-i", str(folder/"frame-board.jpg"), "-filter_complex", "hstack",
        "-frames:v", "1", str(folder/"comparison-board.jpg"))
    run("ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf",
        "select=eq(n\\,96)+eq(n\\,201)+eq(n\\,330),scale=360:640,tile=3x1",
        "-frames:v", "1", str(folder/"phone-check.jpg"))
    qa.update({"integrated_lufs": lufs, "true_peak_dbfs": peak, "audio_channels": 2,
               "motion_by_act": movement(video), "field_luma": field_luma(video)})
    (folder / "qa.json").write_text(json.dumps(qa, indent=2), encoding="utf-8")
    comparison = {
        "before": {"sha256": old["result"]["sha256"], "lufs": old_lufs, "true_peak": old_peak,
                   "motion_by_act": movement(before), "field_luma": field_luma(before)},
        "after": qa, "baseline_unchanged": True,
        "approved_snapshot_unchanged":
            proof["approval"]["current_snapshot_sha256"]
            == old["approval"]["current_snapshot_sha256"],
        "method": "Same-time frame boards, 10 Hz pixel deltas, fixed field ROI, EBU R128",
        "human_artistic_approval": "PENDING",
    }
    assert comparison["approved_snapshot_unchanged"]
    (folder / "comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
