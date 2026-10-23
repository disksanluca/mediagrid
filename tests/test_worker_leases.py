"""A second worker must not steal a live claim during recovery."""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from apps.api.database import SessionLocal
from apps.api.models import Job, JobStatus, now
from apps.api.services import claim_next_job, fence_job_completion, renew_job_lease
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
