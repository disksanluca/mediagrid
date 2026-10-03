from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Channel
from ..schemas import ChannelCreate, ChannelRead
from ..services import record_event

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("", response_model=list[ChannelRead])
def list_channels(db: Session = Depends(get_db)) -> list[Channel]:
    return list(db.scalars(select(Channel).order_by(Channel.created_at.desc())))


@router.post("", response_model=ChannelRead, status_code=status.HTTP_201_CREATED)
def create_channel(payload: ChannelCreate, db: Session = Depends(get_db)) -> Channel:
    channel = Channel(**payload.model_dump())
    db.add(channel)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Channel slug already exists") from exc
    record_event(
        db, "CHANNEL_CREATED", "channel", channel.id, after=payload.model_dump(mode="json")
    )
    db.commit()
    db.refresh(channel)
    return channel


@router.get("/{channel_id}", response_model=ChannelRead)
def get_channel(channel_id: str, db: Session = Depends(get_db)) -> Channel:
    channel = db.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel
