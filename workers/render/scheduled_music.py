"""Fenced local worker for MusicBrainz draft schedules; never publishes."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
from sqlalchemy import and_, or_, select, update

from apps.api.config import get_settings
from apps.api.database import SessionLocal
from apps.api.models import Channel, MusicDraftSchedule
from apps.api.official_music import fetch_release_group, import_release_group
from apps.api.services import record_event

logger = logging.getLogger(__name__)
LEASE_SECONDS = 90


def _utc_now() -> datetime:
    # SQLite stores this column without an offset; PostgreSQL keeps its UTC value.
    return datetime.now(UTC).replace(tzinfo=None)


def _claim_due() -> tuple[str, str, str] | None:
    current = _utc_now()
    token = uuid4().hex
    with SessionLocal() as db:
        expired = db.scalars(select(MusicDraftSchedule).where(
            MusicDraftSchedule.status == "RUNNING",
            MusicDraftSchedule.lease_expires_at <= current,
            MusicDraftSchedule.attempt >= MusicDraftSchedule.max_attempts,
        )).all()
        for item in expired:
            item.status = "FAILED"
            item.error = "Worker lease expired after the final attempt"
            item.lease_token = None
            item.lease_expires_at = None
            record_event(db, "MUSIC_DRAFT_FAILED", "music_draft_schedule", item.id,
                         after={"reason": item.error})
        db.commit()
        candidate = db.scalar(select(MusicDraftSchedule).where(
            MusicDraftSchedule.attempt < MusicDraftSchedule.max_attempts,
            or_(
                and_(MusicDraftSchedule.status == "PENDING",
                     MusicDraftSchedule.run_after <= current),
                and_(MusicDraftSchedule.status == "RUNNING",
                     MusicDraftSchedule.lease_expires_at <= current),
            ),
        ).order_by(MusicDraftSchedule.run_after, MusicDraftSchedule.created_at)
            .with_for_update(skip_locked=True).limit(1))
        if candidate is None:
            return None
        expected_token = candidate.lease_token
        claimed = db.execute(update(MusicDraftSchedule).where(
            MusicDraftSchedule.id == candidate.id,
            MusicDraftSchedule.status == candidate.status,
            MusicDraftSchedule.attempt == candidate.attempt,
            MusicDraftSchedule.lease_token == expected_token,
        ).values(
            status="RUNNING", attempt=candidate.attempt + 1,
            lease_token=token,
            lease_expires_at=current + timedelta(seconds=LEASE_SECONDS),
            error=None,
        ))
        if claimed.rowcount != 1:
            db.rollback()
            return None
        identifier = candidate.id
        release_group_id = candidate.release_group_id
        db.commit()
        return identifier, release_group_id, token


def _fail(schedule_id: str, token: str, reason: str) -> None:
    with SessionLocal() as db:
        item = db.get(MusicDraftSchedule, schedule_id)
        if item is None or item.status != "RUNNING" or item.lease_token != token:
            return
        item.status = "FAILED"
        item.error = reason[:300]
        item.lease_token = None
        item.lease_expires_at = None
        record_event(db, "MUSIC_DRAFT_FAILED", "music_draft_schedule", item.id,
                     after={"reason": item.error})
        db.commit()


def draft_one() -> bool:
    """Create one due source-backed draft; project and success commit atomically."""
    if get_settings().mediagrid_mode != "LOCAL":
        return False
    claimed = _claim_due()
    if claimed is None:
        return False
    schedule_id, identifier, token = claimed
    try:
        record, checked_at = fetch_release_group(UUID(identifier))
        with SessionLocal() as db:
            item = db.scalar(select(MusicDraftSchedule).where(
                MusicDraftSchedule.id == schedule_id,
            ).with_for_update())
            if item is None or item.status != "RUNNING" or item.lease_token != token:
                return True  # cancelled or superseded while the provider was being called
            channel = db.get(Channel, item.channel_id)
            if channel is None or channel.default_engine != "music":
                raise ValueError("Music channel was removed or changed")
            project = import_release_group(db, channel, record, checked_at)
            item.project_id = project.id
            item.status = "SUCCEEDED"
            item.lease_token = None
            item.lease_expires_at = None
            record_event(db, "MUSIC_DRAFT_CREATED", "music_draft_schedule", item.id,
                         after={"project_id": project.id,
                                "source_url": record["source_url"]})
            db.commit()
        return True
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Scheduled MusicBrainz draft failed: %s", exc)
        _fail(schedule_id, token, f"MusicBrainz draft failed: {type(exc).__name__}")
        return True
    except Exception:
        logger.exception("Scheduled MusicBrainz draft failed unexpectedly")
        _fail(schedule_id, token, "Local draft worker failed; inspect the log")
        return True
