"""M4 through the installed service/worker, allowed only on the disposable Windows CI host."""

import argparse
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.motion_engine_media import create_media  # noqa: E402
from scripts.proof_creative_motion import checked  # noqa: E402
from scripts.proof_motion_engine import seed_project, write  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--ffmpeg", required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true" or not os.environ.get("RUNNER_TEMP"):
        raise SystemExit("This installed-app smoke is restricted to the disposable CI runner")
    folder = Path(os.environ["RUNNER_TEMP"]) / "m4-installed-proof"
    folder.mkdir(exist_ok=False)
    files = create_media(folder, "sports", 12, args.ffmpeg)
    with httpx.Client(base_url=f"http://127.0.0.1:{args.port}", timeout=60) as client:
        _, root, request = seed_project(client, "sports", files)
        request["quality"] = "preview"
        preview = checked(client.post(root + "/motion/engine/preview", json=request))
        job = checked(client.post(root + "/motion/engine/render", json=request))
        deadline = time.monotonic() + 420
        while time.monotonic() < deadline:
            job = checked(client.get(f"/api/v1/jobs/{job['id']}"))
            if job["status"] == "SUCCEEDED":
                break
            if job["status"] in {"FAILED", "BLOCKED", "CANCELLED"}:
                raise RuntimeError(job)
            time.sleep(2)
        assert job["status"] == "SUCCEEDED", job
        assert job["result"]["plan_sha256"] == preview["plan_sha256"]
        video = client.get(root + f"/motion/jobs/{job['id']}/video")
        video.raise_for_status()
        (folder / "sports-installed-preview.mp4").write_bytes(video.content)
        review = checked(client.get(root + f"/motion/jobs/{job['id']}/review"))
        assert review["status"] == "AWAITING_HUMAN_REVIEW"
        assert not review["publication_enabled"]
        assert checked(client.get(root + "/review"))["status"] == "APPROVED_STORYBOARD"
        write(folder / "job.json", job)
        print(
            f"Installed M4: real 360-frame H264/AAC preview, job {job['id']}; human review pending"
        )


if __name__ == "__main__":
    main()
