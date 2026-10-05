from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChannelCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    niche: str
    default_engine: Literal["football", "geo", "music"]
    language: str = "pt-BR"
    timezone: str = "America/Sao_Paulo"
    autopilot_level: Literal["MANUAL", "ASSISTED", "AUTO_DRAFT"] = "ASSISTED"
    brand_profile: dict[str, Any] = Field(default_factory=dict)
    editorial_profile: dict[str, Any] = Field(default_factory=dict)


class ChannelRead(ChannelCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class ProjectCreate(BaseModel):
    channel_id: str
    title: str = Field(min_length=2, max_length=240)
    topic: str = Field(min_length=3)
    content_type: str = "video"
    format: Literal["horizontal", "vertical", "square", "carousel"] = "vertical"


class ProjectRead(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    plan: dict[str, Any] | None
    script: dict[str, Any] | None
    edl: dict[str, Any] | None
    error: str | None
    voice_ready: bool
    created_at: datetime
    updated_at: datetime


class Scene(BaseModel):
    id: str
    duration_seconds: float = Field(gt=0, le=60)
    narration: str
    visual_type: Literal["headline", "stat", "map", "image", "quote", "outro"]
    visual_query: str
    on_screen_text: str
    transition: str = "cut"


class ContentPlan(BaseModel):
    project_id: str
    engine: str
    hook: str
    angle: str
    target_duration_seconds: int
    scenes: list[Scene] = Field(min_length=2)
    requires_fact_review: bool = True


class ProjectPlanUpdate(BaseModel):
    scenes: list[Scene] = Field(min_length=2)
    hook: str = Field(min_length=3)
    angle: str = Field(min_length=3)


class ChannelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    brand_profile: dict[str, Any] | None = None
    editorial_profile: dict[str, Any] | None = None


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str | None
    job_type: str
    status: str
    progress: float
    attempt: int
    max_attempts: int
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    media_type: str
    rights_status: str
    creator: str | None
    license_name: str | None
    commercial_use: bool
    metadata_json: dict[str, Any]
    created_at: datetime


class SystemStatus(BaseModel):
    mode: str
    paid_ai_allowed: bool
    database: str
    ffmpeg: bool
    ollama: Literal["CONNECTED", "NOT_CONNECTED"]
    dry_run: bool
    engines: list[str]
    tts: str = "NOT_CONFIGURED"
    transcription: str = "NOT_CONFIGURED"
