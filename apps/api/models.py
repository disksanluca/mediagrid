import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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

    @property
    def voice_ready(self) -> bool:
        from .local_media import voice_matches

        return voice_matches(self.id, self.script)


class ProjectRevision(Base):
    """Immutable saved timeline revision; the legacy project EDL remains renderable."""

    __tablename__ = "project_revisions"
    __table_args__ = (UniqueConstraint("project_id", "revision", name="uq_project_revision"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    edl: Mapped[dict[str, Any]] = mapped_column(JSON)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


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


class UploadSession(TimestampMixin, Base):
    """Durable offset for one local, resumable media import."""

    __tablename__ = "upload_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(240))
    media_type: Mapped[str] = mapped_column(String(40))
    expected_size: Mapped[int] = mapped_column(BigInteger)
    expected_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    received_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(24), default="OPEN")
    rights_status: Mapped[str] = mapped_column(String(40))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    creator: Mapped[str | None] = mapped_column(String(240), nullable=True)
    license_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    commercial_use: Mapped[bool] = mapped_column(Boolean, default=False)
    asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Transcript(TimestampMixin, Base):
    """One versioned transcript per immutable asset source."""

    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), unique=True)
    source_sha256: Mapped[str] = mapped_column(String(64))
    engine: Mapped[str] = mapped_column(String(40))
    model_id: Mapped[str] = mapped_column(String(240))
    model_version: Mapped[str] = mapped_column(String(40))
    language: Mapped[str] = mapped_column(String(20))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(40), default="REVIEW_REQUIRED")
    cues_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class TranscriptWord(Base):
    __tablename__ = "transcript_words"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    transcript_id: Mapped[str] = mapped_column(ForeignKey("transcripts.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    start_ms: Mapped[int] = mapped_column(BigInteger)
    end_ms: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    speaker_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    edited: Mapped[bool] = mapped_column(Boolean, default=False)


class ClipCandidate(TimestampMixin, Base):
    """A suggested original interval with versioned human selection and crop."""

    __tablename__ = "clip_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    source_sha256: Mapped[str] = mapped_column(String(64))
    transcript_revision: Mapped[int] = mapped_column(Integer)
    analysis_version: Mapped[str] = mapped_column(String(40))
    start_ms: Mapped[int] = mapped_column(BigInteger)
    end_ms: Mapped[int] = mapped_column(BigInteger)
    context_start_ms: Mapped[int] = mapped_column(BigInteger)
    context_end_ms: Mapped[int] = mapped_column(BigInteger)
    word_start_index: Mapped[int] = mapped_column(Integer)
    word_end_index: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    reason_codes: Mapped[list[str]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), default="SUGGESTED")
    selected_start_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    selected_end_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    aspect: Mapped[str] = mapped_column(String(20), default="source")
    focus_x: Mapped[float] = mapped_column(Float, default=0.5)
    focus_y: Mapped[float] = mapped_column(Float, default=0.5)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class FootballSequence(TimestampMixin, Base):
    """Versioned human-marked football edit; source hashes pin every shot."""

    __tablename__ = "football_sequences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), unique=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="REVIEW_REQUIRED")
    aspect: Mapped[str] = mapped_column(String(20), default="source")
    shots_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    score_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    score_source_url: Mapped[str | None] = mapped_column(Text, nullable=True)


class KnowledgeClaim(TimestampMixin, Base):
    """One cited factual assertion requiring individual human review."""

    __tablename__ = "knowledge_claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    scene_id: Mapped[str] = mapped_column(String(100))
    text: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    source_title: Mapped[str] = mapped_column(String(240))
    published_at: Mapped[date] = mapped_column(Date)
    support_excerpt: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="REVIEW_REQUIRED")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
