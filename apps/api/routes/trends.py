"""Read-only Wikimedia pageview signals and source-backed local drafts."""

from datetime import date

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Channel
from ..official_trends import fetch_top, import_page, search_top, source_url
from ..schemas import ProjectRead

router = APIRouter(prefix="/trends", tags=["trends"])


class ImportPage(BaseModel):
    channel_id: str
    day: date
    article: str = Field(min_length=1, max_length=140)


@router.get("/wiki-top")
def list_wikipedia_top(
    day: date, query: str = Query(default="", max_length=80),
) -> list[dict[str, str | int]]:
    try:
        source_url(day)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        return search_top(day, query)
    except ValueError as exc:
        raise HTTPException(503, "Wikimedia returned unusable data") from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(503, "Wikimedia data is not available for this day") from exc
        raise HTTPException(503, "Wikimedia is unavailable now") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Wikimedia is unavailable now") from exc


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_from_wikimedia(payload: ImportPage, db: Session = Depends(get_db)):
    channel = db.get(Channel, payload.channel_id)
    if channel is None:
        raise HTTPException(404, "Channel not found")
    if channel.default_engine != "trends":
        raise HTTPException(422, "Select a Trends channel")
    try:
        source_url(payload.day)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        records, checked_at = fetch_top(payload.day)
    except ValueError as exc:
        raise HTTPException(503, "Wikimedia returned unusable data") from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(503, "Wikimedia data is not available for this day") from exc
        raise HTTPException(503, "Wikimedia is unavailable now") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Wikimedia is unavailable now") from exc
    record = next((item for item in records if item["article"] == payload.article), None)
    if record is None:
        raise HTTPException(404, "Page not found in that day's ranking")
    project = import_page(db, channel, record, checked_at)
    db.commit()
    db.refresh(project)
    return project
