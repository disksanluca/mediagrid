import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class ProjectStatus(StrEnum):
    IDEA = "IDEA"
    RESEARCHING = "RESEARCHING"
    RESEARCHED = "RESEARCHED"
    SCRIPTING = "SCRIPTING"
    SCRIPTED = "SCRIPTED"
    ASSETING = "ASSETING"
    AUDIO = "AUDIO"
    EDIT_PLANNING = "EDIT_PLANNING"
    RENDERING = "RENDERING"
    QC = "QC"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    PUBLISHED = "PUBLISHED"
    ANALYZED = "ANALYZED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Channel(TimestampMixin, Base):
    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    niche: Mapped[str] = mapped_column(String(60))
    language: Mapped[str] = mapped_column(String(16), default="pt-BR")
    timezone: Mapped[str] = mapped_column(String(64), default="America/Sao_Paulo")
    default_engine: Mapped[str] = mapped_column(String(60))
    autopilot_level: Mapped[str] = mapped_column(String(40), default="ASSISTED")
    brand_profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    editorial_profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    projects: Mapped[list["Project"]] = relationship(back_populates="channel")


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    topic: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(60), default="video")
    format: Mapped[str] = mapped_column(String(40), default="vertical")
    status: Mapped[str] = mapped_column(String(40), default=ProjectStatus.IDEA.value, index=True)
    plan: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    script: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    edl: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    channel: Mapped[Channel] = relationship(back_populates="projects")
    jobs: Mapped[list["Job"]] = relationship(back_populates="project")


class Asset(TimestampMixin, Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(240))
    media_type: Mapped[str] = mapped_column(String(40), index=True)
    path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    rights_status: Mapped[str] = mapped_column(String(40), default="UNKNOWN")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    creator: Mapped[str | None] = mapped_column(String(240), nullable=True)
    license_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    commercial_use: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    job_type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), default=JobStatus.QUEUED.value, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    progress: Mapped[float] = mapped_column(Float, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project | None] = relationship(back_populates="jobs")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    actor: Mapped[str] = mapped_column(String(120), default="local-user")
    source: Mapped[str] = mapped_column(String(120), default="api")
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PlatformConnection(TimestampMixin, Base):
    __tablename__ = "platform_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id"), index=True)
    platform: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="NOT_CONNECTED")
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
