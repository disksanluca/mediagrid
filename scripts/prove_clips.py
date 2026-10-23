"""Create an isolated technical proof of two human-selected synthetic cuts."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PROOF = ROOT / "data" / "rea-proof" / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-clips"
PROOF.mkdir(parents=True)
os.environ["DATABASE_URL"] = f"sqlite:///{(PROOF / 'mediagrid.db').as_posix()}"
os.environ["MEDIAGRID_DATA_DIR"] = str(PROOF)

from fastapi.testclient import TestClient  # noqa: E402

from apps.api.main import app  # noqa: E402
from apps.api.migrate import main as migrate  # noqa: E402
from workers.render.main import media_one  # noqa: E402


def require(response):
    if not response.is_success:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:1000]}")
    return response.json()


def main() -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required")
    source = PROOF / "synthetic-long.mp4"
    subprocess.run([
        ffmpeg, "-nostdin", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=15:duration=32",
        "-f", "lavfi", "-i", "sine=frequency=330:duration=32",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
        "-shortest", str(source),
    ], check=True, timeout=120)
    migrate()
    with TestClient(app) as client:
        with source.open("rb") as media:
            asset = require(client.post("/api/v1/assets", files={
                "file": (source.name, media, "video/mp4"),
            }, data={"rights_status": "OWNED", "creator": "MediaGrid synthetic proof"}))
        base = f"/api/v1/assets/{asset['id']}"
        words = [{"start_ms": index * 1000, "end_ms": index * 1000 + 900,
                  "text": "frase." if index in {9, 19, 29} else "palavra"}
                 for index in range(30)]
        cues = [{"start_ms": start, "end_ms": start + 9900,
                 "text": f"Frase sintética {start // 10000 + 1}."}
                for start in (0, 10_000, 20_000)]
        saved = require(client.put(f"{base}/transcript-v2", json={
            "expected_revision": 0, "language": "pt", "words": words, "cues": cues,
        }))
        require(client.post(f"{base}/captions/approve", json={
            "expected_revision": saved["revision"],
        }))
        analysis = require(client.post(f"{base}/clips/analyze"))
        assert media_one()
        analysis_job = require(client.get(f"/api/v1/jobs/{analysis['job_id']}"))
        assert analysis_job["status"] == "SUCCEEDED", analysis_job["error"]
        candidates = require(client.get(f"{base}/clips"))
        assert len(candidates) >= 2
        outputs = []
        for index, candidate in enumerate(candidates[:2]):
            url = f"{base}/clips/{candidate['id']}"
            if index == 0:
                candidate = require(client.patch(url, json={
                    "expected_revision": candidate["revision"], "action": "edit",
                    "aspect": "vertical", "focus_x": 0.65,
                }))
            selected = require(client.patch(url, json={
                "expected_revision": candidate["revision"], "action": "select",
            }))
            render = require(client.post(f"{url}/render", json={
                "expected_revision": selected["revision"],
            }))
            assert media_one()
            job = require(client.get(f"/api/v1/jobs/{render['job_id']}"))
            assert job["status"] == "SUCCEEDED", job["error"]
            assert client.get(f"{url}/render/{job['id']}").is_success
            outputs.append(job["result"])
    report = {
        "asset_id": asset["id"],
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "candidate_count": len(candidates),
        "selected_count": len(outputs), "outputs": outputs,
        "proof_dir": str(PROOF),
    }
    (PROOF / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
