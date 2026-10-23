"""A queued job can be cancelled without pretending to stop running work."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from apps.api.database import SessionLocal
from apps.api.models import Asset, Event, Job, JobStatus
from apps.api.services import claim_next_job


def test_queued_and_waiting_jobs_cancel_once(client: TestClient) -> None:
    with SessionLocal() as db:
        queued = Job(job_type="VOICE", payload={})
        waiting = Job(job_type="RENDER", status=JobStatus.WAITING_FOR_WORKER.value,
                      payload={})
        db.add_all([queued, waiting])
        db.commit()
        queued_id, waiting_id = queued.id, waiting.id

    for job_id in (queued_id, waiting_id):
        cancelled = client.post(f"/api/v1/jobs/{job_id}/cancel")
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == JobStatus.CANCELLED.value
        assert client.post(f"/api/v1/jobs/{job_id}/cancel").status_code == 200

    with SessionLocal() as db:
        assert claim_next_job(db, ["VOICE", "RENDER"]) is None
        events = list(db.scalars(select(Event).where(Event.event_type == "JOB_CANCELLED")))
        assert len(events) == 2
        assert {event.entity_id for event in events} == {queued_id, waiting_id}
        assert all(event.before["status"] in {
            JobStatus.QUEUED.value, JobStatus.WAITING_FOR_WORKER.value
        } for event in events)
        assert all(db.get(Job, job_id).finished_at is not None
                   for job_id in (queued_id, waiting_id))


def test_worker_claim_blocks_cancellation(client: TestClient) -> None:
    with SessionLocal() as db:
        db.add(Job(job_type="VOICE", payload={}))
        db.commit()
        claimed = claim_next_job(db, "VOICE")
        assert claimed is not None
        job_id = claimed.id
        db.commit()

    cancelled = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert cancelled.status_code == 409
    with SessionLocal() as db:
        current = db.get(Job, job_id)
        assert current is not None
        assert current.status == JobStatus.RUNNING.value
        assert current.lease_owner is not None
    assert client.post("/api/v1/jobs/no-such-job/cancel").status_code == 404


def test_cancel_proxy_marks_ingest_without_touching_source(client: TestClient) -> None:
    with SessionLocal() as db:
        asset = Asset(name="original.mp4", media_type="video/mp4", path="original.mp4",
                      sha256="a" * 64, metadata_json={"ingest_status": "PROXY_QUEUED"})
        db.add(asset)
        db.flush()
        job = Job(job_type="PROXY", payload={"asset_id": asset.id})
        db.add(job)
        db.commit()
        asset_id, job_id = asset.id, job.id

    assert client.post(f"/api/v1/jobs/{job_id}/cancel").status_code == 200
    with SessionLocal() as db:
        asset = db.get(Asset, asset_id)
        assert asset is not None
        assert asset.metadata_json["ingest_status"] == "CANCELLED"
        assert asset.name == "original.mp4"
    retried = client.post(f"/api/v1/jobs/{job_id}/retry")
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == JobStatus.QUEUED.value
    assert client.post(f"/api/v1/jobs/{job_id}/retry").status_code == 409
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        asset = db.get(Asset, asset_id)
        assert job is not None and asset is not None
        assert job.finished_at is None
        assert job.lease_owner is None
        assert asset.metadata_json["ingest_status"] == "PROXY_QUEUED"
        events = list(db.scalars(select(Event).where(Event.entity_id == job_id)))
        assert len(events) == 2
        assert {event.event_type for event in events} == {"JOB_CANCELLED", "JOB_RETRIED"}
