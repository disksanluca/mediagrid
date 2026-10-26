"""Measured audiovisual QA; no artistic approval is inferred from these numbers."""

import argparse
import array
import json
import math
import re
import statistics
import subprocess
from pathlib import Path


def run(*args):
    return subprocess.run(args, check=True, capture_output=True)


def pcm(path, channels=1):
    samples = array.array("f")
    samples.frombytes(
        run(
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-ac",
            str(channels),
            "-ar",
            "48000",
            "-f",
            "f32le",
            "-",
        ).stdout
    )
    return samples


def qa(folder):
    folder = folder.resolve()
    base = (Path(__file__).resolve().parents[1] / "data/m4-complete-proof").resolve()
    if not folder.is_relative_to(base):
        raise ValueError("QA accepts only disposable M4 proofs")
    proof = json.loads((folder / "proof.json").read_text(encoding="utf-8"))
    label = proof["label"]
    video = folder / f"{label}-motion.mp4"
    probe = json.loads(
        run(
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(video),
        ).stdout
    )
    (folder / "ffprobe.json").write_text(json.dumps(probe, indent=2), encoding="utf-8")
    black = run(
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(video),
        "-vf",
        "blackdetect=d=0.03:pix_th=0.02:pic_th=0.98",
        "-an",
        "-f",
        "null",
        "-",
    )
    intervals = re.findall(
        r"black_start:([\d.]+) black_end:([\d.]+)", black.stderr.decode(errors="replace")
    )
    raw = run(
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(video),
        "-vf",
        "scale=96:96,format=gray",
        "-an",
        "-f",
        "rawvideo",
        "-",
    ).stdout
    frames = [raw[i : i + 9216] for i in range(0, len(raw), 9216)]
    deltas = [
        sum(abs(x - y) for x, y in zip(a, b, strict=True)) / 9216
        for a, b in zip(frames, frames[1:], strict=False)
    ]
    static_run = max_static = 0
    for delta in deltas:
        static_run = static_run + 1 if delta < 0.1 else 0
        max_static = max(max_static, static_run)
    audio, source = pcm(video), pcm(folder / "score.wav")
    stereo = pcm(video, 2)
    peak = max(abs(v) for v in stereo)
    rms = math.sqrt(sum(v * v for v in stereo) / len(stereo))
    payload = json.loads((folder / "derived-plan.json").read_text(encoding="utf-8"))
    loudness_run = run(
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(video),
        "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
        "-f",
        "null",
        "-",
    )
    loudness_log = loudness_run.stderr.decode(errors="replace")
    loudness = json.JSONDecoder().raw_decode(loudness_log[loudness_log.rfind("{") :])[0]
    (folder / "loudness.json").write_text(json.dumps(loudness, indent=2), encoding="utf-8")
    stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
    color = {
        k: stream.get(k, "unknown")
        for k in ("color_space", "color_transfer", "color_primaries", "color_range", "pix_fmt")
    }
    sounds = [
        item
        for track in payload["plan"]["edl_v2"]["tracks"]
        if track["kind"] == "music"
        for item in track["items"]
    ]
    sync = []
    # Compare 0.2..0.5 s after each scene boundary with the authored waveform.
    # Sample-resolution lag search in a ±10 ms window, evaluated at 4 kHz;
    # not musical intent, beat quality or human perception.
    for sound in sounds:
        start = round((sound["start_ms"] + 200) * 48)
        offset = round((sound["source_in_ms"] + 200) * 48)
        reference = source[offset : offset + 14400 : 12]
        candidates = []
        for lag_samples in range(-480, 481):
            segment = audio[start + lag_samples : start + lag_samples + 14400 : 12]
            dot = sum(a * b for a, b in zip(reference, segment, strict=True))
            norm = math.sqrt(sum(a * a for a in reference) * sum(b * b for b in segment))
            candidates.append((dot / norm if norm else 0, lag_samples / 48))
        correlation, lag = max(candidates)
        sync.append(
            {
                "cue_start_ms": sound["start_ms"],
                "best_lag_ms": round(lag, 6),
                "correlation": round(correlation, 6),
            }
        )
    seconds = float(probe["format"]["duration"])
    run(
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-i",
        str(video),
        "-vf",
        f"fps=6/{seconds},scale=320:-1,tile=6x1",
        "-frames:v",
        "1",
        str(folder / "frames.png"),
    )
    result = {
        "label": label,
        "decoded_frames": len(frames),
        "black_intervals": intervals,
        "mean_frame_delta_8bit": round(statistics.mean(deltas), 4),
        "median_frame_delta_8bit": round(statistics.median(deltas), 4),
        "longest_run_below_0_1_seconds": round(max_static / 30, 4),
        "decoded_audio_seconds": len(audio) / 48000,
        "audio_peak_dbfs": round(20 * math.log10(peak), 3),
        "audio_rms_dbfs": round(20 * math.log10(rms), 3),
        "integrated_lufs": float(loudness["input_i"]),
        "true_peak_dbtp": float(loudness["input_tp"]),
        "loudness_range_lu": float(loudness["input_lra"]),
        "color": color,
        "source_alignment": sync,
        "human_artistic_review": "PENDING",
        "limitations": (
            "Motion metrics are not artistic scores. "
            "AAC alignment measured at 1/48000 s steps within ±10 ms."
        ),
    }
    (folder / "qa.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    assert not intervals, intervals
    assert len(frames) == payload["plan"]["render"]["frames"]
    assert peak < 1 and rms > 0.001
    assert -24 <= float(loudness["input_i"]) <= -12, loudness
    assert float(loudness["input_tp"]) <= -1, loudness
    if payload["plan"]["render"].get("color_space") == "bt709":
        assert color == dict(
            color_space="bt709",
            color_transfer="bt709",
            color_primaries="bt709",
            color_range="tv",
            pix_fmt="yuv420p",
        ), color
    assert all(abs(s["best_lag_ms"]) <= 5 and s["correlation"] > 0.95 for s in sync), sync
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folders", type=Path, nargs="+")
    for path in parser.parse_args().folders:
        qa(path)
