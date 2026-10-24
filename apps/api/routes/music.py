"""Read-only MusicBrainz metadata research and source-backed local drafts."""

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Channel
from ..official_music import fetch_release_group, import_release_group, search_release_groups
from ..schemas import ProjectRead

router = APIRouter(prefix="/music", tags=["music"])


class ImportReleaseGroup(BaseModel):
    channel_id: str
    release_group_id: UUID


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
