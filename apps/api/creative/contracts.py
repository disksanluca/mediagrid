"""Strict versioned contracts for creative data, separate from the existing EDL."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceRef(StrictModel):
    url: HttpUrl
    title: str = Field(min_length=2, max_length=200)
    fact_reviewed: bool = False


class CreativeBrief(StrictModel):
    schema_version: Literal["brief_v1"] = "brief_v1"
    topic: str = Field(min_length=3, max_length=500)
    audience: str = Field(min_length=2, max_length=240)
    objective: str = Field(min_length=5, max_length=600)
    format: Literal["vertical", "horizontal", "square"] = "vertical"
    duration_ms: int = Field(ge=3000, le=600000)
    fps: Literal[24, 25, 30, 60] = 30
    language: str = Field(min_length=2, max_length=16, default="pt-BR")
    factual_mode: Literal["FICTIONAL", "FACT_CHECK_REQUIRED"] = "FACT_CHECK_REQUIRED"
    sources: list[SourceRef] = Field(default_factory=list, max_length=30)
    asset_ids: list[str] = Field(default_factory=list, max_length=100)
    restrictions: list[str] = Field(default_factory=list, max_length=30)
    style_notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def distinct_assets(self) -> "CreativeBrief":
        if len(self.asset_ids) != len(set(self.asset_ids)):
            raise ValueError("asset_ids must be unique")
        return self


class CreativeDNA(StrictModel):
    schema_version: Literal["creative_dna_v1"] = "creative_dna_v1"
    palette: list[str] = Field(min_length=2, max_length=8)
    font_display: str = Field(min_length=2, max_length=120)
    font_body: str = Field(min_length=2, max_length=120)
    tone: str = Field(min_length=2, max_length=240)
    energy: Literal["restrained", "balanced", "intense"] = "balanced"
    must_have: list[str] = Field(default_factory=list, max_length=30)
    avoid: list[str] = Field(default_factory=list, max_length=30)
    max_words_per_card: int = Field(default=10, ge=1, le=40)

    @model_validator(mode="after")
    def valid_palette(self) -> "CreativeDNA":
        if any(not re.fullmatch(r"#[0-9a-fA-F]{6}", color) for color in self.palette):
            raise ValueError("palette needs six-digit hex colors")
        return self


class CreativeDirection(StrictModel):
    id: str = Field(min_length=2, max_length=60)
    title: str = Field(min_length=3, max_length=120)
    thesis: str = Field(min_length=10, max_length=600)
    rationale: str = Field(min_length=10, max_length=2000)
    emotional_arc: str = Field(min_length=5, max_length=240)
    rhythm: Literal["slow", "dynamic", "hybrid"]
    typography: str = Field(min_length=2, max_length=120)
    composition: str = Field(min_length=5, max_length=240)
    motion_language: str = Field(min_length=5, max_length=240)
    palette: list[str] = Field(min_length=2, max_length=8)
    estimated_complexity: Literal["LOW", "MEDIUM", "HIGH"]


class CreativeDirectionSet(StrictModel):
    schema_version: Literal["directions_v1"] = "directions_v1"
    directions: list[CreativeDirection] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def distinct_directions(self) -> "CreativeDirectionSet":
        if len({direction.id for direction in self.directions}) != 3:
            raise ValueError("three distinct direction IDs required")
        return self


class StoryboardShot(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    start_ms: int = Field(ge=0)
    duration_ms: int = Field(gt=0)
    beat: str = Field(min_length=3, max_length=240)
    on_screen_text: str = Field(default="", max_length=160)
    visual_description: str = Field(min_length=8, max_length=1000)
    camera_intent: str = Field(default="Static", min_length=2, max_length=200)
    motion_intent: str = Field(default="Static", min_length=2, max_length=200)
    audio_cue: str = Field(default="", max_length=200)
    asset_ids: list[str] = Field(default_factory=list, max_length=20)
    claim_ids: list[str] = Field(default_factory=list, max_length=20)


class CreativeStoryboard(StrictModel):
    schema_version: Literal["storyboard_v1"] = "storyboard_v1"
    direction_id: str = Field(min_length=2, max_length=60)
    duration_ms: int = Field(ge=3000, le=600000)
    fps: Literal[24, 25, 30, 60] = 30
    shots: list[StoryboardShot] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def contiguous_shots(self) -> "CreativeStoryboard":
        seen: set[str] = set()
        cursor = 0
        for shot in self.shots:
            if shot.id in seen:
                raise ValueError("duplicate shot id")
            if len(shot.asset_ids) != len(set(shot.asset_ids)):
                raise ValueError(f"shot {shot.id} repeats an asset")
            if len(shot.claim_ids) != len(set(shot.claim_ids)):
                raise ValueError(f"shot {shot.id} repeats a claim")
            seen.add(shot.id)
            if shot.start_ms != cursor:
                raise ValueError(f"shot {shot.id} must start at {cursor} ms")
            cursor += shot.duration_ms
        if cursor != self.duration_ms:
            raise ValueError("shots must fill storyboard duration")
        return self


class RevisionWrite(StrictModel):
    expected_revision: int = Field(ge=0)


class CreativeDNAWrite(RevisionWrite):
    content: CreativeDNA


class CreativeBriefWrite(RevisionWrite):
    content: CreativeBrief


class CreativeDirectionsWrite(RevisionWrite):
    expected_brief_revision: int = Field(ge=1)
    expected_dna_revision: int = Field(ge=1)


class CreativeStoryboardWrite(RevisionWrite):
    expected_direction_revision: int = Field(ge=1)
    content: CreativeStoryboard


class CreativeDecisionWrite(RevisionWrite):
    expected_storyboard_revision: int = Field(ge=1)
    expected_snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: Literal["APPROVE", "REVISE", "REJECT"]
    actor: str = Field(min_length=2, max_length=120)
    notes: str = Field(default="", max_length=2000)
    storyboard_reviewed: bool = False
    rights_checked: bool = False
    facts_checked: bool = False
