from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ChannelCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    niche: str
    default_engine: Literal["football", "geo", "music", "clips", "politics", "trends"]
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
    transition: Literal["impact", "slide", "cut", "zoom", "fade"] = "cut"
    asset_id: str | None = None
    clip_start_seconds: float = Field(default=0, ge=0, le=21600)
    clip_end_seconds: float | None = Field(default=None, gt=0, le=21600)

    @model_validator(mode="after")
    def valid_clip_range(self) -> "Scene":
        if self.clip_end_seconds is not None and self.clip_end_seconds <= self.clip_start_seconds:
            raise ValueError("O fim do trecho deve ser maior que o início.")
        return self


class ContentPlan(BaseModel):
    project_id: str
    engine: str
    origin: Literal["OUTLINE", "BRIEF_BASED", "OFFICIAL_SOURCE", "LOCAL_AI", "MANUAL"] = "OUTLINE"
    hook: str
    angle: str
    target_duration_seconds: int
    scenes: list[Scene] = Field(min_length=2)
    requires_fact_review: bool = True
    review_checks: list[str] = Field(default_factory=list)
    source_refs: list[dict[str, str]] = Field(default_factory=list)


class ProjectPlanUpdate(BaseModel):
    scenes: list[Scene] = Field(min_length=2)
    hook: str = Field(min_length=3)
    angle: str = Field(min_length=3)


class ProjectReview(BaseModel):
    source_urls: list[HttpUrl] = Field(min_length=1)
    facts_confirmed: bool
    rights_confirmed: bool
    notes: str = Field(min_length=3, max_length=2000)
    caption: str | None = Field(default=None, min_length=3, max_length=2200)


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


class AssetRightsUpdate(BaseModel):
    rights_status: Literal["UNKNOWN", "OWNED", "LICENSED", "RESTRICTED"]
    creator: str | None = Field(default=None, max_length=240)
    license_name: str | None = Field(default=None, max_length=120)
    commercial_use: bool = False


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
