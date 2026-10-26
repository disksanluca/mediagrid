"""Strict public requests shared by the compiler API and generated clients."""

from typing import Literal

from pydantic import Field

from .models import Contract, Identifier, RecipeRef


class EngineParameters(Contract):
    text_scale: float = Field(default=1, ge=0.85, le=1.15)
    audio_gain: float = Field(default=0.8, gt=0, le=1)
    diagnostics: bool = False


class EngineRequest(Contract):
    expected_storyboard_revision: int = Field(ge=1)
    expected_snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    recipe: RecipeRef
    asset_bindings: dict[Identifier, Identifier] = Field(max_length=32)
    parameters: EngineParameters = Field(default_factory=EngineParameters)
    quality: Literal["preview", "final"] = "preview"
