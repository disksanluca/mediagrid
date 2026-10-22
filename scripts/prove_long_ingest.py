"""Generate an isolated, synthetic 90-second ingestion and timeline proof."""

import copy
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
PROOF = ROOT / "data" / "rea-proof" / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-ingest"
PROOF.mkdir(parents=True)
os.environ["DATABASE_URL"] = f"sqlite:///{(PROOF / 'mediagrid.db').as_posix()}"
os.environ["MEDIAGRID_DATA_DIR"] = str(PROOF)

from fastapi.testclient import TestClient  # noqa: E402

from apps.api.main import app  # noqa: E402
from apps.api.migrate import main as migrate  # noqa: E402
from workers.render.main import media_one  # noqa: E402


def digest(path: Path) -> str:
    hash_value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hash_value.update(chunk)
    return hash_value.hexdigest()


def require(response):
    if not response.is_success:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:1000]}")
    return response.json()


def main() -> None:
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("FFmpeg and FFprobe are required for this local proof")
    started = time.perf_counter()
    source = PROOF / "synthetic-90s.mp4"
    subprocess.run([
        ffmpeg, "-nostdin", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=15:duration=90",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=90",
        "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "900k",
        "-c:a", "aac", "-b:a", "64k", "-shortest", str(source),
    ], check=True, timeout=300)
    source_hash = digest(source)
    migrate()
    base = "/api/v1"
    with TestClient(app) as client:
        upload = require(client.post(f"{base}/assets/uploads", json={
            "name": source.name, "media_type": "video/mp4",
            "size_bytes": source.stat().st_size, "sha256": source_hash,
            "rights_status": "OWNED", "creator": "MediaGrid synthetic proof",
            "commercial_use": False,
        }))
        upload_url = f"{base}/assets/uploads/{upload['id']}"
        split = min(8 * 1024 * 1024, source.stat().st_size // 2)
        with source.open("rb") as stream:
            first_chunk = client.put(
                upload_url, headers={"Upload-Offset": "0"}, content=stream.read(split)
            )
            require(first_chunk)
    with TestClient(app) as reconnected:
        state = require(reconnected.get(upload_url))
        assert state["received_bytes"] == split
        with source.open("rb") as stream:
            stream.seek(split)
            offset = split
            while block := stream.read(8 * 1024 * 1024):
                state = require(reconnected.put(
                    upload_url, headers={"Upload-Offset": str(offset)}, content=block,
                ))
                offset += len(block)
        completed = require(reconnected.post(f"{upload_url}/complete"))
        asset_id, job_id = completed["asset_id"], completed["proxy_job_id"]
        assert job_id
        channel = require(reconnected.post(f"{base}/channels", json={
            "name": "Prova sintética", "slug": "prova-sintetica",
            "niche": "Teste", "default_engine": "clips",
        }))
        project = require(reconnected.post(f"{base}/projects", json={
            "channel_id": channel["id"], "title": "Ingestão local de 90 segundos",
            "topic": "Primeira frase de teste. Segunda frase de teste. Terceira frase de teste.",
        }))
        project_id = project["id"]
        plan = require(reconnected.post(f"{base}/projects/{project_id}/plan"))
        for index, scene in enumerate(plan["scenes"], start=1):
            scene["narration"] = f"Esta é a cena sintética número {index}."
        require(reconnected.put(f"{base}/projects/{project_id}/plan", json={
            "scenes": plan["scenes"], "hook": plan["hook"], "angle": plan["angle"],
        }))
        timeline = require(reconnected.get(f"{base}/projects/{project_id}/edl-v2"))
        edl = timeline["edl"]
        edl["tracks"].append({
            "id": "synthetic-source", "kind": "video", "items": [{
                "id": "synthetic-cutaway", "start_ms": 0, "duration_ms": 1000,
                "z_index": 5, "source_asset_id": asset_id,
                "source_in_ms": 12000, "source_out_ms": 13000,
                "speed": 1, "preset": "video_overlay_v1",
                "params": {"focus_x": 0.5, "focus_y": 0.5, "opacity": 1},
            }],
        })
        invalid = copy.deepcopy(edl)
        invalid["tracks"][-1]["items"][0]["source_in_ms"] = 90000
        invalid["tracks"][-1]["items"][0]["source_out_ms"] = 91000
        assert reconnected.put(f"{base}/projects/{project_id}/edl-v2", json={
            "expected_revision": timeline["revision"],
            "expected_legacy_sha256": timeline["legacy_sha256"],
            "edl": invalid,
        }).status_code == 422
        require(reconnected.put(f"{base}/projects/{project_id}/edl-v2", json={
            "expected_revision": timeline["revision"],
            "expected_legacy_sha256": timeline["legacy_sha256"],
            "edl": edl,
        }))
        preview = require(reconnected.get(f"{base}/projects/{project_id}/preview"))
        assert preview["revision"] == timeline["revision"] + 1
    assert media_one()
    with TestClient(app) as client:
        asset = next(a for a in require(client.get(f"{base}/assets")) if a["id"] == asset_id)
        job = next(j for j in require(client.get(f"{base}/jobs")) if j["id"] == job_id)
        assert job["status"] == "SUCCEEDED"
        assert asset["metadata_json"]["proxy_sha256"]
        assert client.get(f"{base}/assets/{asset_id}/proxy").status_code == 200
        assert client.get(f"{base}/assets/{asset_id}/waveform").status_code == 200
    original_store = PROOF / "assets" / asset_id
    proxy = PROOF / "proxies" / f"{asset_id}.mp4"
    assert digest(original_store) == source_hash
    assert digest(proxy) == asset["metadata_json"]["proxy_sha256"]
    manifest = {
        "sample": "SYNTHETIC_TEST_ONLY", "duration_seconds": 90,
        "upload_id": upload["id"], "asset_id": asset_id,
        "project_id": project_id, "proxy_job_id": job_id,
        "source_sha256": source_hash, "stored_source_sha256": digest(original_store),
        "proxy_sha256": digest(proxy), "waveform_status": asset["metadata_json"]["waveform_status"],
        "source_bytes": source.stat().st_size, "proxy_bytes": proxy.stat().st_size,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "review": "Technical pipeline only; no editorial or publication approval",
    }
    (PROOF / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"proof": str(PROOF), **manifest}, indent=2))


if __name__ == "__main__":
    main()
