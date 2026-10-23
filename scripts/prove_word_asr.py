"""Run local speech, API, database and worker through an isolated caption proof."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def require(response):
    if not response.is_success:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:1000]}")
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--ffmpeg-path", type=Path)
    args = parser.parse_args()
    model = args.model_dir.resolve()
    if not (model / "model.bin").is_file():
        raise RuntimeError("Provide an already downloaded faster-whisper model directory")
    proof = ROOT / "data" / "rea-proof" / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-asr"
    proof.mkdir(parents=True)
    os.environ["DATABASE_URL"] = f"sqlite:///{(proof / 'mediagrid.db').as_posix()}"
    os.environ["MEDIAGRID_DATA_DIR"] = str(proof)
    os.environ["MEDIAGRID_ASR_MODEL_DIR"] = str(model)
    if args.ffmpeg_path:
        os.environ["MEDIAGRID_FFMPEG_PATH"] = str(args.ffmpeg_path.resolve())

    from fastapi.testclient import TestClient

    from apps.api.local_media import synthesize_voice
    from apps.api.main import app
    from apps.api.migrate import main as migrate
    from workers.render.main import media_one

    wav = proof / "synthetic-voice.wav"
    synthesize_voice(
        "Este arquivo de teste verifica a transcricao local e as legendas corrigiveis.", wav
    )
    video = proof / "synthetic-spoken.mp4"
    ffmpeg = str(args.ffmpeg_path.resolve()) if args.ffmpeg_path else shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required")
    subprocess.run([
        ffmpeg, "-nostdin", "-y", "-v", "error", "-f", "lavfi", "-i",
        "testsrc2=size=640x360:rate=15", "-i", str(wav),
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
        "-shortest", str(video),
    ], check=True, timeout=120)
    source_hash = hashlib.sha256(video.read_bytes()).hexdigest()
    migrate()
    start = time.perf_counter()
    with TestClient(app) as client:
        with video.open("rb") as source:
            asset = require(client.post("/api/v1/assets", files={
                "file": (video.name, source, "video/mp4"),
            }, data={"rights_status": "OWNED", "creator": "MediaGrid synthetic proof"}))
        queued = require(client.post(f"/api/v1/assets/{asset['id']}/transcribe-words"))
        assert media_one()
        job = require(client.get(f"/api/v1/jobs/{queued['job_id']}"))
        if job["status"] != "SUCCEEDED":
            raise RuntimeError(f"ASR worker failed: {job['error']}")
        transcript = require(client.get(f"/api/v1/assets/{asset['id']}/transcript-v2"))
        assert transcript["source_sha256"] == source_hash
        assert transcript["words"] and transcript["cues"]
        assert transcript["status"] == "REVIEW_REQUIRED"
        review = require(client.post(f"/api/v1/assets/{asset['id']}/captions/approve", json={
            "expected_revision": transcript["revision"],
        }))
        srt = client.get(f"/api/v1/assets/{asset['id']}/captions.srt")
        assert srt.is_success and srt.text.startswith("1\n")
        (proof / "captions.srt").write_text(srt.text, encoding="utf-8")
        render = require(client.post(f"/api/v1/assets/{asset['id']}/captions/render", json={
            "expected_revision": review["revision"],
        }))
        assert media_one()
        caption_job = require(client.get(f"/api/v1/jobs/{render['job_id']}"))
        if caption_job["status"] != "SUCCEEDED":
            raise RuntimeError(f"Caption worker failed: {caption_job['error']}")
        caption_mp4 = client.get(f"/api/v1/assets/{asset['id']}/captions/render/{render['job_id']}")
        assert caption_mp4.is_success and caption_mp4.content.startswith(b"\x00\x00")
        rendered = Path(caption_job["result"]["output"])
        assert hashlib.sha256(rendered.read_bytes()).hexdigest() == caption_job["result"]["sha256"]
    report = {
        "asset_id": asset["id"], "job_id": queued["job_id"],
        "source_sha256": source_hash, "status": review["status"],
        "word_count": len(transcript["words"]), "cue_count": len(transcript["cues"]),
        "language": transcript["language"], "model_version": transcript["model_version"],
        "caption_video_sha256": caption_job["result"]["sha256"],
        "caption_video_duration_ms": caption_job["result"]["duration_ms"],
        "elapsed_seconds": round(time.perf_counter() - start, 2),
        "proof_dir": str(proof),
    }
    (proof / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
