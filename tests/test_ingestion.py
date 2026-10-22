"""Real local MP4 import: durable resume, integrity, proxy, and worker state."""

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.config import get_settings
from apps.api.database import SessionLocal
from apps.api.main import app
from apps.api.models import Asset, Job, UploadSession
from workers.render.main import media_one


def synthetic_mp4(path: Path) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("Local FFmpeg is unavailable")
    subprocess.run([
        ffmpeg, "-nostdin", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=15:duration=4",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
        "-shortest", str(path),
    ], check=True, capture_output=True, timeout=90)
    return path.read_bytes()


def test_resume_import_and_real_proxy(client: TestClient, tmp_path: Path) -> None:
    original = synthetic_mp4(tmp_path / "synthetic.mp4")
    digest = hashlib.sha256(original).hexdigest()
    base = "/api/v1/assets"
    created = client.post(f"{base}/uploads", json={
        "name": "synthetic.mp4", "media_type": "video/mp4",
        "size_bytes": len(original), "sha256": digest,
        "rights_status": "OWNED", "creator": "MediaGrid synthetic test",
        "commercial_use": False,
    })
    assert created.status_code == 201, created.text
    upload_id = created.json()["id"]
    url = f"{base}/uploads/{upload_id}"
    first = len(original) // 3
    sent = client.put(url, headers={"Upload-Offset": "0"}, content=original[:first])
    assert sent.status_code == 200, sent.text
    assert sent.json()["received_bytes"] == first
    with TestClient(app) as reconnected:
        assert reconnected.get(url).json()["received_bytes"] == first
        repeated = reconnected.put(
            url, headers={"Upload-Offset": "0"}, content=original[:first]
        )
        assert repeated.status_code == 200
        assert repeated.json()["received_bytes"] == first
        wrong = reconnected.put(url, headers={"Upload-Offset": "0"}, content=b"wrong")
        assert wrong.status_code == 409
        remainder = reconnected.put(
            url, headers={"Upload-Offset": str(first)}, content=original[first:]
        )
        assert remainder.status_code == 200, remainder.text
        assert remainder.json()["received_bytes"] == len(original)
        done = reconnected.post(f"{url}/complete")
        assert done.status_code == 200, done.text
        asset_id = done.json()["asset_id"]
        job_id = done.json()["proxy_job_id"]
        assert reconnected.post(f"{url}/complete").json()["asset_id"] == asset_id
        assert reconnected.get(f"{base}/{asset_id}/proxy").status_code == 409
    assert media_one() is True
    with SessionLocal() as db:
        asset = db.get(Asset, asset_id)
        job = db.get(Job, job_id)
        session = db.get(UploadSession, upload_id)
        assert asset and asset.sha256 == digest
        assert asset.metadata_json["duration_ms"] >= 3900
        assert asset.metadata_json["proxy_sha256"]
        assert asset.metadata_json["waveform_status"] == "READY"
        assert job and job.status == "SUCCEEDED" and job.progress == 1
        assert session and session.status == "COMPLETE"
    store = get_settings().mediagrid_data_dir
    assert hashlib.sha256((store / "assets" / asset_id).read_bytes()).hexdigest() == digest
    assert client.get(f"{base}/{asset_id}/proxy").status_code == 200
    assert client.get(f"{base}/{asset_id}/waveform").status_code == 200


def test_declared_hash_mismatch_rejects_import(client: TestClient, tmp_path: Path) -> None:
    original = synthetic_mp4(tmp_path / "incorrect.mp4")
    url = "/api/v1/assets/uploads"
    created = client.post(url, json={
        "name": "incorrect.mp4", "size_bytes": len(original),
        "sha256": "0" * 64,
    })
    assert created.status_code == 201
    upload_url = f"{url}/{created.json()['id']}"
    sent = client.put(upload_url, headers={"Upload-Offset": "0"}, content=original)
    assert sent.status_code == 200
    rejected = client.post(f"{upload_url}/complete")
    assert rejected.status_code == 422
    assert client.get(upload_url).json()["status"] == "FAILED"
    assert not any(
        asset["sha256"] == hashlib.sha256(original).hexdigest()
        for asset in client.get("/api/v1/assets").json()
    )


def test_proxy_failure_is_visible_and_retry_recovers(
    client: TestClient, tmp_path: Path
) -> None:
    original = synthetic_mp4(tmp_path / "retry.mp4")
    base = "/api/v1/assets"
    upload = client.post(f"{base}/uploads", json={
        "name": "retry.mp4", "size_bytes": len(original), "rights_status": "OWNED",
    }).json()
    url = f"{base}/uploads/{upload['id']}"
    assert client.put(url, headers={"Upload-Offset": "0"}, content=original).status_code == 200
    done = client.post(f"{url}/complete").json()
    asset_id, job_id = done["asset_id"], done["proxy_job_id"]
    store = get_settings().mediagrid_data_dir / "assets" / asset_id
    store.write_bytes(b"damaged")
    assert media_one() is True
    assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "FAILED"
    asset = next(a for a in client.get(base).json() if a["id"] == asset_id)
    assert asset["metadata_json"]["ingest_status"] == "FAILED"
    assert client.get(f"{base}/{asset_id}/proxy").status_code == 409
    store.write_bytes(original)
    assert client.post(f"/api/v1/jobs/{job_id}/retry").status_code == 200
    assert media_one() is True
    assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "SUCCEEDED"
    assert client.get(f"{base}/{asset_id}/proxy").status_code == 200
