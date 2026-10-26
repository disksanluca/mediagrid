"""Re-render an immutable disposable plan using the SAME worker, without replacing its job."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    folder = args.folder.resolve()
    if not folder.is_relative_to((ROOT / "data/m4-complete-proof").resolve()):
        parser.error("Only disposable M4 proof directories are allowed")
    proof = json.loads((folder / "proof.json").read_text(encoding="utf-8"))
    output = folder / "repeat-c1.mp4"
    if output.exists():
        parser.error("Repeat output already exists")
    os.environ.update(
        {
            "DATABASE_URL": "sqlite:///" + (folder.parent / "workspace.db").as_posix(),
            "MEDIAGRID_DATA_DIR": str(folder.parent),
            "MEDIAGRID_RENDERER_ROOT": str(ROOT / "apps/renderer"),
            "MEDIAGRID_NODE_PATH": shutil.which("node") or "",
            "MEDIAGRID_RENDER_CONCURRENCY": "1",
        }
    )
    from apps.api.database import SessionLocal
    from apps.api.models import Job
    from workers.render.creative_motion import render_creative_motion

    stop = folder / "repeat.stop"
    sampler = (
        subprocess.Popen(
            [
                shutil.which("pwsh") or "powershell",
                "-NoProfile",
                "-File",
                str(ROOT / "scripts/measure-motion-process.ps1"),
                "-RootProcessId",
                str(os.getpid()),
                "-StopPath",
                str(stop),
                "-OutputPath",
                str(folder / "repeat-performance.json"),
            ],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if os.name == "nt"
        else None
    )
    try:
        with SessionLocal() as db:
            job = db.get(Job, proof["job"]["id"])
            original = json.dumps(job.payload, sort_keys=True)
            result = render_creative_motion(db, job, str(uuid4()), output)
            assert json.dumps(job.payload, sort_keys=True) == original
            db.rollback()
        result["same_encoded_sha256"] = result["sha256"] == proof["job"]["result"]["sha256"]
        (folder / "repeat.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "same_encoded_sha256": result["same_encoded_sha256"],
                    "seconds": result["render_seconds"],
                    "sha256": result["sha256"],
                }
            )
        )
        reference = folder / f"{proof['label']}-motion.mp4"
        comparison = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                str(reference),
                "-i",
                str(output),
                "-lavfi",
                "psnr",
                "-f",
                "null",
                "-",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        match = re.search(r"average:([\d.]+|inf) min:([\d.]+|inf)", comparison.stderr)
        assert match, comparison.stderr
        result["decoded_video_psnr_average_db"] = float(match[1]) if match[1] != "inf" else None
        result["decoded_video_psnr_min_db"] = float(match[2]) if match[2] != "inf" else None
        hashes = []
        for video in (reference, output):
            hashes.append(
                subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-i",
                        str(video),
                        "-map",
                        "0:a:0",
                        "-f",
                        "hash",
                        "-hash",
                        "sha256",
                        "-",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
            )
        result["decoded_audio_identical"] = hashes[0] == hashes[1]
        result["reproducibility_tolerance"] = "Decoded video PSNR >= 50 dB; identical decoded audio"
        (folder / "repeat.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        assert float(match[2]) >= 50 and result["decoded_audio_identical"], result
    finally:
        if sampler:
            stop.touch()
            sampler.wait(timeout=20)
            stop.unlink()


if __name__ == "__main__":
    main()
