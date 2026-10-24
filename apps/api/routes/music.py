"""MusicBrainz research, immediate drafts and scheduled local draft requests."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import Channel, MusicDraftSchedule
from ..official_music import fetch_release_group, import_release_group, search_release_groups
from ..schemas import ProjectRead
from ..services import record_event

router = APIRouter(prefix="/music", tags=["music"])


class ImportReleaseGroup(BaseModel):
    channel_id: str
    release_group_id: UUID


class ScheduleReleaseGroup(ImportReleaseGroup):
    scheduled_at: datetime


def schedule_state(item: MusicDraftSchedule) -> dict:
    return {
        "id": item.id, "channel_id": item.channel_id,
        "release_group_id": item.release_group_id,
        "scheduled_at": item.scheduled_at.replace(tzinfo=UTC).isoformat(),
        "status": item.status, "attempt": item.attempt,
        "max_attempts": item.max_attempts, "project_id": item.project_id,
        "error": item.error,
    }


@router.get("/release-groups")
def list_release_groups(
    query: str = Query(min_length=3, max_length=80),
) -> list[dict[str, str]]:
    try:
        return search_release_groups(query)
    except ValueError as exc:
        raise HTTPException(503, "MusicBrainz returned unusable metadata") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(503, "MusicBrainz is unavailable now") from exc


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_from_musicbrainz(payload: ImportReleaseGroup, db: Session = Depends(get_db)):
    channel = db.get(Channel, payload.channel_id)
    if channel is None:
        raise HTTPException(404, "Channel not found")
    if channel.default_engine != "music":
        raise HTTPException(422, "Select a Music channel")
    try:
        record, checked_at = fetch_release_group(payload.release_group_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(404, "Release group not found in MusicBrainz") from exc
        raise HTTPException(503, "MusicBrainz is unavailable now") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "MusicBrainz returned unusable metadata") from exc
    project = import_release_group(db, channel, record, checked_at)
    db.commit()
    db.refresh(project)
    return project


@router.get("/drafts/schedules")
def list_draft_schedules(db: Session = Depends(get_db)) -> list[dict]:
    if get_settings().mediagrid_mode != "LOCAL":
        raise HTTPException(503, "Scheduled drafts require the local desktop worker")
    items = db.scalars(select(MusicDraftSchedule).order_by(
        MusicDraftSchedule.created_at.desc(),
    ).limit(100))
    return [schedule_state(item) for item in items]


@router.post("/drafts/schedules", status_code=status.HTTP_201_CREATED)
def schedule_release_group(payload: ScheduleReleaseGroup, db: Session = Depends(get_db)) -> dict:
    if get_settings().mediagrid_mode != "LOCAL":
        raise HTTPException(503, "Scheduled drafts require the local desktop worker")
    channel = db.get(Channel, payload.channel_id)
    if channel is None:
        raise HTTPException(404, "Channel not found")
    if channel.default_engine != "music":
        raise HTTPException(422, "Select a Music channel")
    if payload.scheduled_at.tzinfo is None:
        raise HTTPException(422, "Scheduled time requires a timezone")
    utc_time = payload.scheduled_at.astimezone(UTC).replace(tzinfo=None)
    identifier = str(payload.release_group_id)
    existing = db.scalar(select(MusicDraftSchedule).where(
        MusicDraftSchedule.channel_id == channel.id,
        MusicDraftSchedule.release_group_id == identifier,
        MusicDraftSchedule.scheduled_at == utc_time,
    ))
    if existing:
        return schedule_state(existing)
    delay = utc_time - datetime.now(UTC).replace(tzinfo=None)
    if not timedelta(seconds=10) <= delay <= timedelta(days=30):
        raise HTTPException(422, "Choose a time from 10 seconds to 30 days ahead")
    item = MusicDraftSchedule(
        channel_id=channel.id, release_group_id=identifier,
        scheduled_at=utc_time, run_after=utc_time, status="PENDING",
        attempt=0, max_attempts=3,
    )
    db.add(item)
    try:
        db.flush()
        record_event(db, "MUSIC_DRAFT_SCHEDULED", "music_draft_schedule", item.id,
                     after={"release_group_id": identifier,
                            "scheduled_at": utc_time.replace(tzinfo=UTC).isoformat()})
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(MusicDraftSchedule).where(
            MusicDraftSchedule.channel_id == channel.id,
            MusicDraftSchedule.release_group_id == identifier,
            MusicDraftSchedule.scheduled_at == utc_time,
        ))
        if existing is None:
            raise HTTPException(409, "Scheduled request conflicted") from None
        return schedule_state(existing)
    db.refresh(item)
    return schedule_state(item)


@router.post("/drafts/schedules/{schedule_id}/cancel")
def cancel_draft_schedule(schedule_id: str, db: Session = Depends(get_db)) -> dict:
    if get_settings().mediagrid_mode != "LOCAL":
        raise HTTPException(503, "Scheduled drafts require the local desktop worker")
    item = db.get(MusicDraftSchedule, schedule_id)
    if item is None:
        raise HTTPException(404, "Schedule not found")
    if item.status == "CANCELLED":
        return schedule_state(item)
    changed = db.execute(update(MusicDraftSchedule).where(
        MusicDraftSchedule.id == schedule_id,
        MusicDraftSchedule.status.in_(["PENDING", "RUNNING"]),
        MusicDraftSchedule.project_id.is_(None),
    ).values(status="CANCELLED", lease_token=None, lease_expires_at=None))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Only a pending draft can be cancelled")
    record_event(db, "MUSIC_DRAFT_CANCELLED", "music_draft_schedule", item.id)
    db.commit()
    db.refresh(item)
    return schedule_state(item)


@router.post("/drafts/schedules/{schedule_id}/retry")
def retry_draft_schedule(schedule_id: str, db: Session = Depends(get_db)) -> dict:
    if get_settings().mediagrid_mode != "LOCAL":
        raise HTTPException(503, "Scheduled drafts require the local desktop worker")
    item = db.get(MusicDraftSchedule, schedule_id)
    if item is None:
        raise HTTPException(404, "Schedule not found")
    if item.status != "FAILED" or item.attempt >= item.max_attempts:
        raise HTTPException(409, "This draft is not retryable")
    item.status = "PENDING"
    item.run_after = datetime.now(UTC).replace(tzinfo=None)
    item.error = None
    record_event(db, "MUSIC_DRAFT_RETRIED", "music_draft_schedule", item.id)
    db.commit()
    db.refresh(item)
    return schedule_state(item)
