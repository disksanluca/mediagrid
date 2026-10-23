"""A second worker must not steal a live claim during recovery."""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier

import pytest

from apps.api.database import SessionLocal
from apps.api.models import Job, JobStatus, Project, ProjectStatus, now
from apps.api.services import claim_next_job, fence_job_completion, renew_job_lease
from workers.render.artifacts import (
    finish_media_render_attempt,
    finish_render_attempt,
    finish_voice_attempt,
)
from workers.render.lease import start_lease_heartbeat
from workers.render.main import recover_interrupted_jobs


def test_claim_and_recover_only_expired_leases() -> None:
    with SessionLocal() as db:
        first = Job(job_type="VOICE", payload={})
        second = Job(job_type="VOICE", payload={})
        db.add_all([first, second])
        db.commit()
        first_id, second_id = first.id, second.id

    with SessionLocal() as db:
        claimed = claim_next_job(db, "VOICE", worker_id="desktop-a")
        assert claimed is not None and claimed.id == first_id
        assert claimed.status == JobStatus.RUNNING.value
        assert claimed.attempt == 1
        assert claimed.lease_owner.startswith("desktop-a:")
        claim_token = claimed.lease_owner
        assert claimed.lease_expires_at is not None
        assert claimed.heartbeat_at is not None
        original_expiry = claimed.lease_expires_at
        db.commit()
        assert not renew_job_lease(db, first_id, "desktop-b")
        assert renew_job_lease(db, first_id, claim_token, ttl_seconds=600)
        db.commit()
        db.refresh(claimed)
        assert claimed.lease_expires_at is not None
        assert original_expiry is not None
        assert claimed.lease_expires_at.replace(tzinfo=None) > original_expiry.replace(tzinfo=None)
        other = claim_next_job(db, ["VOICE"], worker_id="desktop-b")
        assert other is not None and other.id == second_id
        assert other.lease_owner.startswith("desktop-b:")
        db.commit()
        assert claim_next_job(db, "VOICE") is None

    with SessionLocal() as db:
        expired = db.get(Job, first_id)
        assert expired is not None
        expired.lease_expires_at = now() - timedelta(seconds=1)
        db.commit()
    recover_interrupted_jobs()
    with SessionLocal() as db:
        expired = db.get(Job, first_id)
        live = db.get(Job, second_id)
        assert expired is not None and live is not None
        assert expired.status == JobStatus.QUEUED.value
        assert expired.lease_owner is None
        assert live.status == JobStatus.RUNNING.value
        assert live.lease_owner.startswith("desktop-b:")


def test_heartbeat_renews_long_running_job() -> None:
    with SessionLocal() as db:
        db.add(Job(job_type="RENDER", payload={}))
        db.commit()
        claimed = claim_next_job(db, "RENDER", worker_id="desktop-c")
        assert claimed is not None
        job_id = claimed.id
        claim_token = claimed.lease_owner
        first_heartbeat = claimed.heartbeat_at
        assert first_heartbeat is not None
        db.commit()
    stop_heartbeat = start_lease_heartbeat(job_id, claim_token, interval_seconds=0.03)
    renewed = False
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        with SessionLocal() as db:
            current = db.get(Job, job_id)
            assert current is not None
            if (current.heartbeat_at and current.heartbeat_at.replace(tzinfo=None)
                    > first_heartbeat.replace(tzinfo=None)):
                current.status = JobStatus.SUCCEEDED.value
                db.commit()
                renewed = True
                break
        time.sleep(0.03)
    assert renewed
    stop_heartbeat()


def test_stale_worker_cannot_commit_after_reclaim() -> None:
    with SessionLocal() as db:
        db.add(Job(job_type="RENDER", payload={}))
        db.commit()
        stale = claim_next_job(db, "RENDER", worker_id="same-process")
        assert stale is not None
        job_id, old_token = stale.id, stale.lease_owner
        db.commit()

        with SessionLocal() as other:
            expired = other.get(Job, job_id)
            assert expired is not None
            expired.lease_expires_at = now() - timedelta(seconds=1)
            other.commit()
        recover_interrupted_jobs()
        with SessionLocal() as other:
            fresh = claim_next_job(other, "RENDER", worker_id="same-process")
            assert fresh is not None
            assert fresh.lease_owner != old_token
            new_token = fresh.lease_owner
            other.commit()

        stale.status = JobStatus.SUCCEEDED.value
        stale.result = {"output": "stale.mp4"}
        assert not fence_job_completion(db, job_id, old_token)
        db.rollback()

    with SessionLocal() as db:
        current = db.get(Job, job_id)
        assert current is not None
        assert current.status == JobStatus.RUNNING.value
        assert current.lease_owner == new_token
        assert current.result is None
        current.status = JobStatus.SUCCEEDED.value
        current.result = {"output": "fresh.mp4"}
        assert fence_job_completion(db, job_id, new_token)
        db.commit()

    with SessionLocal() as db:
        completed = db.get(Job, job_id)
        assert completed is not None
        assert completed.status == JobStatus.SUCCEEDED.value
        assert completed.result == {"output": "fresh.mp4"}
        assert completed.lease_owner is None


def test_simultaneous_sqlite_claims_do_not_duplicate_work() -> None:
    with SessionLocal() as db:
        db.add(Job(job_type="VOICE", payload={}))
        db.commit()
    barrier = Barrier(2)

    def claim(worker: str) -> str | None:
        with SessionLocal() as db:
            barrier.wait(timeout=5)
            job = claim_next_job(db, "VOICE", worker_id=worker)
            claimed_id = job.id if job else None
            db.commit()
            return claimed_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(claim, worker) for worker in ("a", "b")]
        claims = [future.result(timeout=10) for future in futures]
    assert len([job_id for job_id in claims if job_id]) == 1


def test_stale_render_cannot_replace_newer_project_video(client, tmp_path: Path) -> None:
    channel = client.post("/api/v1/channels", json={
        "name": "Render lease", "slug": "render-lease", "niche": "Teste",
        "default_engine": "music",
    }).json()
    project_id = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Vídeo isolado",
        "topic": "Compara promoção de artefatos por lease",
    }).json()["id"]
    final = tmp_path / "renders" / f"{project_id}.mp4"
    final.parent.mkdir()
    final.write_bytes(b"previous-approved-output")
    with SessionLocal() as db:
        db.add(Job(project_id=project_id, job_type="RENDER", payload={}))
        db.commit()
        stale = claim_next_job(db, "RENDER", worker_id="render-a")
        assert stale is not None
        job_id, old_token = stale.id, stale.lease_owner
        project = db.get(Project, project_id)
        assert project is not None
        db.commit()
        with SessionLocal() as other:
            claimed = other.get(Job, job_id)
            assert claimed is not None
            claimed.lease_expires_at = now() - timedelta(seconds=1)
            other.commit()
        recover_interrupted_jobs()
        with SessionLocal() as other:
            fresh = claim_next_job(other, "RENDER", worker_id="render-b")
            assert fresh is not None
            new_token = fresh.lease_owner
            other.commit()
        stale_stage = tmp_path / "stale-attempt.mp4"
        stale_stage.write_bytes(b"stale-video")
        stale.status = JobStatus.SUCCEEDED.value
        project.status = ProjectStatus.QC.value
        assert not finish_render_attempt(
            db, stale, project, old_token, stale_stage, final,
        )
        assert not stale_stage.exists()
        assert final.read_bytes() == b"previous-approved-output"

    with SessionLocal() as db:
        fresh = db.get(Job, job_id)
        project = db.get(Project, project_id)
        assert fresh is not None and project is not None
        fresh_stage = tmp_path / "fresh-attempt.mp4"
        fresh_stage.write_bytes(b"fresh-video")
        fresh.status = JobStatus.SUCCEEDED.value
        fresh.result = {"output": str(final)}
        project.status = ProjectStatus.QC.value
        assert finish_render_attempt(db, fresh, project, new_token, fresh_stage, final)
        assert not fresh_stage.exists()
    assert final.read_bytes() == b"fresh-video"
    with SessionLocal() as db:
        completed = db.get(Job, job_id)
        assert completed is not None
        assert completed.status == JobStatus.SUCCEEDED.value
        assert completed.lease_owner is None


def test_missing_staged_render_cannot_report_success(client, tmp_path: Path) -> None:
    channel = client.post("/api/v1/channels", json={
        "name": "Render failure", "slug": "render-failure", "niche": "Teste",
        "default_engine": "music",
    }).json()
    project_id = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Falha de arquivo",
        "topic": "O arquivo temporário não existe",
    }).json()["id"]
    final = tmp_path / "renders" / f"{project_id}.mp4"
    final.parent.mkdir()
    with SessionLocal() as db:
        db.add(Job(project_id=project_id, job_type="RENDER", payload={}))
        db.commit()
        job = claim_next_job(db, "RENDER", worker_id="render-c")
        assert job is not None
        token = job.lease_owner
        project = db.get(Project, project_id)
        assert project is not None
        db.commit()
        job.status = JobStatus.SUCCEEDED.value
        project.status = ProjectStatus.QC.value
        assert finish_render_attempt(db, job, project, token,
                                     tmp_path / "missing.mp4", final)
    with SessionLocal() as db:
        failed = db.get(Job, job.id)
        project = db.get(Project, project_id)
        assert failed is not None and project is not None
        assert failed.status == JobStatus.FAILED.value
        assert failed.result is None
        assert project.status == ProjectStatus.FAILED.value
        assert not final.exists()


@pytest.mark.parametrize("job_type", [
    "CAPTION_RENDER", "CLIP_RENDER", "FOOTBALL_RENDER", "NARRATIVE_3D_RENDER",
])
def test_stale_media_render_cannot_replace_newer_video(
    client, tmp_path: Path, job_type: str,
) -> None:
    channel = client.post("/api/v1/channels", json={
        "name": "Media lease", "slug": "media-lease", "niche": "Teste",
        "default_engine": "music",
    }).json()
    project_id = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Arquivo de mídia",
        "topic": "Tentativa antiga não pode trocar o MP4",
    }).json()["id"]
    final = tmp_path / f"{job_type}.mp4"
    final.write_bytes(b"previous-video")
    with SessionLocal() as db:
        db.add(Job(project_id=project_id, job_type=job_type, payload={}))
        db.commit()
        stale = claim_next_job(db, job_type, worker_id="media-a")
        assert stale is not None
        job_id, old_token = stale.id, stale.lease_owner
        db.commit()
        with SessionLocal() as other:
            claimed = other.get(Job, job_id)
            assert claimed is not None
            claimed.lease_expires_at = now() - timedelta(seconds=1)
            other.commit()
        recover_interrupted_jobs()
        with SessionLocal() as other:
            fresh = claim_next_job(other, job_type, worker_id="media-b")
            assert fresh is not None
            new_token = fresh.lease_owner
            other.commit()
        stage = tmp_path / "old.mp4"
        stage.write_bytes(b"old-attempt")
        stale.status = JobStatus.SUCCEEDED.value
        stale.result = {"output": str(final)}
        assert not finish_media_render_attempt(db, stale, old_token, stage, final)
        assert not stage.exists()
        assert final.read_bytes() == b"previous-video"
    with SessionLocal() as db:
        fresh = db.get(Job, job_id)
        assert fresh is not None
        stage = tmp_path / "new.mp4"
        stage.write_bytes(b"new-attempt")
        fresh.status = JobStatus.SUCCEEDED.value
        fresh.result = {"output": str(final)}
        assert finish_media_render_attempt(db, fresh, new_token, stage, final)
        assert not stage.exists()
    assert final.read_bytes() == b"new-attempt"


def test_stale_voice_cannot_replace_project_audio(client, tmp_path: Path) -> None:
    channel = client.post("/api/v1/channels", json={
        "name": "Voice lease", "slug": "voice-lease", "niche": "Teste",
        "default_engine": "music",
    }).json()
    project_id = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Voz isolada",
        "topic": "Tentativa de síntese antiga",
    }).json()["id"]
    final_audio = tmp_path / "voice.wav"
    final_manifest = tmp_path / "voice.sha256"
    final_audio.write_bytes(b"previous-voice")
    final_manifest.write_text("previous-script")
    with SessionLocal() as db:
        db.add(Job(project_id=project_id, job_type="VOICE", payload={}))
        db.commit()
        stale = claim_next_job(db, "VOICE", worker_id="voice-a")
        assert stale is not None
        job_id, old_token = stale.id, stale.lease_owner
        db.commit()
        with SessionLocal() as other:
            claimed = other.get(Job, job_id)
            assert claimed is not None
            claimed.lease_expires_at = now() - timedelta(seconds=1)
            other.commit()
        recover_interrupted_jobs()
        with SessionLocal() as other:
            fresh = claim_next_job(other, "VOICE", worker_id="voice-b")
            assert fresh is not None
            new_token = fresh.lease_owner
            other.commit()
        old_audio, old_manifest = tmp_path / "old.wav", tmp_path / "old.sha256"
        old_audio.write_bytes(b"stale-voice")
        old_manifest.write_text("stale-script")
        stale.status = JobStatus.SUCCEEDED.value
        assert not finish_voice_attempt(
            db, stale, old_token, old_audio, final_audio,
            old_manifest, final_manifest,
        )
        assert not old_audio.exists() and not old_manifest.exists()
        assert final_audio.read_bytes() == b"previous-voice"
        assert final_manifest.read_text() == "previous-script"
    with SessionLocal() as db:
        fresh = db.get(Job, job_id)
        assert fresh is not None
        new_audio, new_manifest = tmp_path / "new.wav", tmp_path / "new.sha256"
        new_audio.write_bytes(b"fresh-voice")
        new_manifest.write_text("fresh-script")
        fresh.status = JobStatus.SUCCEEDED.value
        assert finish_voice_attempt(
            db, fresh, new_token, new_audio, final_audio,
            new_manifest, final_manifest,
        )
    assert final_audio.read_bytes() == b"fresh-voice"
    assert final_manifest.read_text() == "fresh-script"


def test_missing_voice_manifest_preserves_prior_audio(client, tmp_path: Path) -> None:
    channel = client.post("/api/v1/channels", json={
        "name": "Voice manifest", "slug": "voice-manifest", "niche": "Teste",
        "default_engine": "music",
    }).json()
    project_id = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Marcador ausente",
        "topic": "Falha antes da promoção",
    }).json()["id"]
    final_audio = tmp_path / "voice.wav"
    final_manifest = tmp_path / "voice.sha256"
    final_audio.write_bytes(b"previous-voice")
    final_manifest.write_text("previous-script")
    with SessionLocal() as db:
        db.add(Job(project_id=project_id, job_type="VOICE", payload={}))
        db.commit()
        job = claim_next_job(db, "VOICE", worker_id="voice-c")
        assert job is not None
        token = job.lease_owner
        db.commit()
        stage = tmp_path / "new.wav"
        stage.write_bytes(b"incomplete-voice")
        job.status = JobStatus.SUCCEEDED.value
        assert finish_voice_attempt(
            db, job, token, stage, final_audio,
            tmp_path / "missing.sha256", final_manifest,
        )
    assert final_audio.read_bytes() == b"previous-voice"
    assert final_manifest.read_text() == "previous-script"
    with SessionLocal() as db:
        failed = db.get(Job, job.id)
        assert failed is not None
        assert failed.status == JobStatus.FAILED.value
        assert failed.result is None
