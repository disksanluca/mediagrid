"""Closed resolved render data. Media paths are supplied only by trusted staging."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .models import Contract, Identifier, MotionScene

Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
Text = Annotated[str, Field(min_length=1, max_length=260)]


class MotionSceneSpec(Contract):
    schema_version: Literal["motion_scene_render_v1"]
    graph: MotionScene
    palette: list[Color] = Field(min_length=2, max_length=8)
    fonts: list[Literal["Barlow Condensed", "Space Grotesk", "IBM Plex Sans"]] = Field(
        min_length=2, max_length=2
    )
    texts: dict[Identifier, Text] = Field(
        max_length=128, json_schema_extra={"additionalProperties": False}
    )
    assets: dict[Identifier, Identifier] = Field(
        max_length=32, json_schema_extra={"additionalProperties": False}
    )
    diagnostics: bool = False

    @model_validator(mode="after")
    def resolved(self):
        from .validation import bindings_in, slots_used

        if set(self.texts) != {n.id for n in self.graph.nodes if n.type == "text"}:
            raise ValueError("Resolved text keys must match text nodes")
        if set(self.assets) != {slot for slot, _ in slots_used(self.graph)}:
            raise ValueError("Resolved asset keys must match graph slots")
        for binding in bindings_in(self.graph):
            if binding.kind == "dna_palette" and binding.index >= len(self.palette):
                raise ValueError("Missing palette entry")
        return self
