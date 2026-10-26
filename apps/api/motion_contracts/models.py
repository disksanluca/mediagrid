"""Closed, strict M4.A data vocabulary. No arbitrary CSS, expressions or media URLs."""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from .canonical import canonical_bytes

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Version = Annotated[str, Field(pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$",
                               max_length=30)]
Number = Annotated[float, Field(ge=-8192, le=8192)]
Unit = Annotated[float, Field(ge=0, le=1)]
ScaleNumber = Annotated[float, Field(ge=0.05, le=8)]
Angle = Annotated[float, Field(ge=-360, le=360)]
Millis = Annotated[int, Field(ge=0, le=30000)]


def valid_position(value):
    if not -600 <= value[2] <= 4000:
        raise ValueError("Position z must be in [-600, 4000]")
    return value


Position = Annotated[list[Number], Field(min_length=3, max_length=3),
                     AfterValidator(valid_position)]
Scale = Annotated[list[ScaleNumber], Field(min_length=2, max_length=2)]
Point = Annotated[list[Number], Field(min_length=2, max_length=2)]
Interval = Annotated[list[Millis], Field(min_length=2, max_length=2)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False,
                              validate_default=True, frozen=True, revalidate_instances="always")


class ShotText(Contract):
    kind: Literal["shot_field"]
    field: Literal["on_screen_text"]


class ClaimText(Contract):
    kind: Literal["approved_claim_field"]
    claim_id: Identifier
    field: Literal["text", "source_label"]


TextBinding = Annotated[ShotText | ClaimText, Field(discriminator="kind")]


class PaletteBinding(Contract):
    kind: Literal["dna_palette"] = "dna_palette"
    index: int = Field(ge=0, le=7)


class FontBinding(Contract):
    kind: Literal["dna_font"] = "dna_font"
    index: int = Field(ge=0, le=1)


class AbsoluteTime(Contract):
    kind: Literal["ms"]
    at_ms: Millis


class CueTime(Contract):
    kind: Literal["cue"]
    cue_ref: Identifier
    offset_ms: int = Field(default=0, ge=-30000, le=30000)


TimeRef = Annotated[AbsoluteTime | CueTime, Field(discriminator="kind")]


class Bezier(Contract):
    kind: Literal["cubic_bezier"]
    # No implicit overshoot: intermediate values stay inside endpoint bounds.
    controls: list[Unit] = Field(min_length=4, max_length=4)


Easing = Literal["linear", "hold", "cubic_in_out", "cubic_out"] | Bezier


class Frame(Contract):
    time: TimeRef
    easing: Easing = "linear"


class PositionFrame(Frame):
    value: Position


class ScaleFrame(Frame):
    value: Scale


class UnitFrame(Frame):
    value: Unit


class AngleFrame(Frame):
    value: Angle


class PositionAnimation(Contract):
    property: Literal["position"]
    keyframes: list[PositionFrame] = Field(min_length=2, max_length=32)


class ScaleAnimation(Contract):
    property: Literal["scale"]
    keyframes: list[ScaleFrame] = Field(min_length=2, max_length=32)


class UnitAnimation(Contract):
    property: Literal["opacity", "progress", "draw_progress"]
    keyframes: list[UnitFrame] = Field(min_length=2, max_length=32)


class AngleAnimation(Contract):
    property: Literal["rotate_z"]
    keyframes: list[AngleFrame] = Field(min_length=2, max_length=32)


Animation = Annotated[
    PositionAnimation | ScaleAnimation | UnitAnimation | AngleAnimation,
    Field(discriminator="property"),
]


class Transform(Contract):
    position: Position = Field(default_factory=lambda: [0, 0, 0])
    scale: Scale = Field(default_factory=lambda: [1, 1])
    rotate_z: Angle = 0
    opacity: Unit = 1
    animations: list[Animation] = Field(default_factory=list, max_length=8)


class NodeBase(Transform):
    id: Identifier
    parent_id: Identifier | None = None
    space: Literal["world", "screen"] = "world"
    z_index: int = Field(default=0, ge=-512, le=512)
    anchor: list[Unit] = Field(default_factory=lambda: [0, 0], min_length=2, max_length=2)
    active_ms: Interval | None = None


class GroupNode(NodeBase):
    type: Literal["group"]


class TextParams(Contract):
    text: TextBinding
    font: FontBinding
    fill: PaletteBinding
    size: float = Field(ge=32, le=512)
    max_width: float = Field(gt=0, le=1920)
    line_height: float = Field(default=1, ge=0.8, le=2)
    max_lines: int = Field(default=6, ge=1, le=6)
    align: Literal["left", "center", "right"] = "left"
    method: Literal["fade_slide"] = "fade_slide"


class TextNode(NodeBase):
    type: Literal["text"]
    params: TextParams


class BoxGeometry(Contract):
    kind: Literal["rect", "ellipse"]
    width: float = Field(gt=0, le=8192)
    height: float = Field(gt=0, le=8192)


class PathGeometry(Contract):
    kind: Literal["polygon", "polyline"]
    points: list[Point] = Field(min_length=2, max_length=512)

    @model_validator(mode="after")
    def polygon(self):
        if self.kind == "polygon" and len(self.points) < 3:
            raise ValueError("Polygon needs at least three points")
        return self


Geometry = Annotated[BoxGeometry | PathGeometry, Field(discriminator="kind")]


class ShapeParams(Contract):
    geometry: Geometry
    fill: PaletteBinding | None = None
    stroke: PaletteBinding | None = None
    stroke_width: float = Field(default=1, ge=0.1, le=64)
    draw_progress: Unit = 1

    @model_validator(mode="after")
    def visible_style(self):
        if self.fill is None and self.stroke is None:
            raise ValueError("Shape needs a fill or stroke")
        if self.geometry.kind == "polyline" and self.stroke is None:
            raise ValueError("Polyline needs a stroke")
        return self


class ShapeNode(NodeBase):
    type: Literal["shape"]
    params: ShapeParams


class MaskParams(Contract):
    target_id: Identifier
    geometry: Geometry
    progress: Unit = 1


class MaskNode(NodeBase):
    type: Literal["mask"]
    params: MaskParams


class FollowerParams(Contract):
    path_ref: Identifier
    progress: Unit = 0
    marker: BoxGeometry
    fill: PaletteBinding


class PathFollowerNode(NodeBase):
    type: Literal["path_follower"]
    params: FollowerParams


class ImageParams(Contract):
    asset_binding: Identifier
    width: float = Field(gt=0, le=4096)
    height: float = Field(gt=0, le=4096)
    fit: Literal["contain", "cover"] = "contain"


class ImageNode(NodeBase):
    type: Literal["image"]
    params: ImageParams


class VideoParams(ImageParams):
    source_in_ms: int = Field(default=0, ge=0, le=600000)
    muted: Literal[True] = True

    @field_validator("muted", mode="before")
    @classmethod
    def strict_muted(cls, value):
        if type(value) is not bool:
            raise ValueError("muted must be a boolean")
        return value


class VideoNode(NodeBase):
    type: Literal["video"]
    params: VideoParams


class ParticleParams(Contract):
    seed: int = Field(ge=0, le=2**31-1)
    count: int = Field(ge=1, le=64)
    velocity: Point
    radius: float = Field(ge=1, le=32)
    fill: PaletteBinding


class ParticleNode(NodeBase):
    type: Literal["particle"]
    params: ParticleParams


class SweepParams(Contract):
    width: float = Field(ge=1, le=2048)
    angle: Angle = 0
    intensity: Unit = 0.5
    blur: float = Field(default=0, ge=0, le=12)
    fill: PaletteBinding


class LightSweepNode(NodeBase):
    type: Literal["light_sweep"]
    params: SweepParams


Node = Annotated[
    GroupNode | TextNode | ShapeNode | MaskNode | PathFollowerNode | ImageNode
    | VideoNode | ParticleNode | LightSweepNode,
    Field(discriminator="type"),
]


class Camera(Contract):
    position: Position = Field(default_factory=lambda: [0, 0, 0])
    rotate_z: Angle = 0
    focal_length: float = Field(default=1200, ge=800, le=2400)
    animations: list[Annotated[PositionAnimation | AngleAnimation,
                               Field(discriminator="property")]] = Field(
                                   default_factory=list, max_length=2)


class SafeArea(Contract):
    left: int = Field(default=72, ge=0, le=960)
    right: int = Field(default=72, ge=0, le=960)
    top: int = Field(default=120, ge=0, le=960)
    bottom: int = Field(default=180, ge=0, le=960)


class SoundCue(Contract):
    asset_binding: Identifier
    source_in_ms: int = Field(default=0, ge=0, le=600000)
    duration_ms: int = Field(gt=0, le=30000)
    gain: float = Field(default=1, gt=0, le=1)
    fade_in_ms: Millis = 0
    fade_out_ms: Millis = 0

    @model_validator(mode="after")
    def fades(self):
        if self.fade_in_ms + self.fade_out_ms > self.duration_ms:
            raise ValueError("Sound fades exceed duration")
        return self


class Cue(Contract):
    id: Identifier
    at_ms: Millis
    sound: SoundCue | None = None


class MotionScene(Contract):
    schema_version: Literal["motion_scene_v1"]
    safe_area: SafeArea = Field(default_factory=SafeArea)
    camera: Camera = Field(default_factory=Camera)
    nodes: list[Node] = Field(min_length=1, max_length=128)
    cues: list[Cue] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def graph(self):
        from .validation import validate_graph
        validate_graph(self)
        canonical_bytes(self)
        return self


class MotionCanvas(Contract):
    width: int = Field(ge=1080, le=1920)
    height: int = Field(ge=1080, le=1920)
    fps_num: int = Field(default=30, ge=30, le=30)
    fps_den: int = Field(default=1, ge=1, le=1)

    @model_validator(mode="after")
    def supported(self):
        if (self.width, self.height) not in {(1080, 1920), (1920, 1080), (1080, 1080)}:
            raise ValueError("Unsupported M4 canvas")
        return self


class Expected(Contract):
    storyboard_revision: int = Field(ge=1)
    snapshot_sha256: Digest
    canvas: MotionCanvas
    duration_ms: int = Field(ge=3000, le=30000)


class RecipeRef(Contract):
    id: Identifier
    version: Version
    sha256: Digest


class MediaBinding(Contract):
    asset_id: Identifier
    sha256: Digest
    byte_size: int = Field(gt=0, le=128*1024*1024)


class ImageBinding(MediaBinding):
    kind: Literal["image"]
    width: int = Field(gt=0, le=4096)
    height: int = Field(gt=0, le=4096)


class AudioBinding(MediaBinding):
    kind: Literal["audio"]
    duration_ms: int = Field(gt=0, le=600000)
    sample_rate: int = Field(ge=8000, le=96000)
    channels: int = Field(ge=1, le=2)


class VideoBinding(MediaBinding):
    kind: Literal["video"]
    width: int = Field(gt=0, le=3840)
    height: int = Field(gt=0, le=3840)
    duration_ms: int = Field(gt=0, le=600000)
    fps_num: int = Field(default=30, ge=30, le=30)
    fps_den: int = Field(default=1, ge=1, le=1)


AssetBinding = Annotated[ImageBinding | AudioBinding | VideoBinding, Field(discriminator="kind")]


class SceneBinding(Contract):
    shot_id: Identifier
    graph: MotionScene


class MotionComposition(Contract):
    schema_version: Literal["motion_composition_v1"]
    project_id: Identifier
    expected: Expected
    recipe: RecipeRef
    asset_bindings: dict[Identifier, AssetBinding] = Field(
        default_factory=dict, max_length=32, json_schema_extra={"additionalProperties": False})
    scenes: list[SceneBinding] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def envelope(self):
        from .validation import validate_envelope
        validate_envelope(self)
        canonical_bytes(self)
        return self


class RecipeScene(Contract):
    shot_slot: Identifier
    # An assertion for binding to the EDL, not a second editable timeline.
    required_duration_ms: int = Field(ge=67, le=30000)
    graph: MotionScene


class MotionRecipe(Contract):
    schema_version: Literal["motion_recipe_v1"]
    id: Identifier
    version: Version
    sha256: Digest
    canvas: MotionCanvas
    asset_slots: dict[Identifier, Literal["image", "audio", "video"]] = Field(
        default_factory=dict, max_length=32, json_schema_extra={"additionalProperties": False})
    scenes: list[RecipeScene] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def recipe(self):
        from .validation import validate_recipe
        validate_recipe(self)
        canonical_bytes(self)
        return self
