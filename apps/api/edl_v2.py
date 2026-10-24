"""Versioned EDL with a strict v1 scene projection and supported v2 layers."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Canvas(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: int = Field(gt=0, le=7680)
    height: int = Field(gt=0, le=7680)
    fps_num: int = Field(gt=0)
    fps_den: int = Field(gt=0)


class TimelineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    duration_ms: int = Field(gt=0)
    z_index: int = 0
    source_asset_id: str | None = None
    source_in_ms: int | None = Field(default=None, ge=0)
    source_out_ms: int | None = Field(default=None, gt=0)
    speed: float = Field(default=1, gt=0, le=8)
    preset: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def source_range(self) -> "TimelineItem":
        if (self.source_in_ms is None) != (self.source_out_ms is None):
            raise ValueError("source in/out must be supplied together")
        if self.source_in_ms is not None:
            if not self.source_asset_id or self.source_out_ms <= self.source_in_ms:
                raise ValueError("source range needs an asset and positive span")
            source_duration = (self.source_out_ms - self.source_in_ms) / self.speed
            if self.params.get("loop") is not True and (
                abs(source_duration - self.duration_ms) > 1000 / 24
            ):
                raise ValueError("source range and timeline duration differ")
        return self


class TimelineTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: Literal["video", "voice", "music", "sfx", "caption", "graphic"]
    items: list[TimelineItem] = Field(default_factory=list)


class OverlayKeyframe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    at_ms: int = Field(ge=0)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    opacity: float = Field(ge=0, le=1)
    scale: float = Field(ge=0.25, le=4)


class OverlaySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=180)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    keyframes: list[OverlayKeyframe] = Field(min_length=2, max_length=8)

    @model_validator(mode="after")
    def nonempty_text(self) -> "OverlaySpec":
        if not self.text.strip():
            raise ValueError("Overlay text must not be blank")
        return self


class MotionCardSpec(OverlaySpec):
    text: str = Field(min_length=1, max_length=60)
    label: str = Field(min_length=1, max_length=24)
    body: str = Field(min_length=1, max_length=100)
    layout: Literal["stack", "split"] = "stack"

    @model_validator(mode="after")
    def safe_area(self) -> "MotionCardSpec":
        if not self.label.strip() or not self.body.strip():
            raise ValueError("Motion card text must not be blank")
        if any(abs(frame.x - 0.5) > 0.01 or abs(frame.y - 0.5) > 0.01
               or not 0.75 <= frame.scale <= 1.05 for frame in self.keyframes):
            raise ValueError("Motion cards must remain centered inside the safe area")
        return self


class FlowDiagramSpec(OverlaySpec):
    text: str = Field(min_length=1, max_length=60)
    steps: list[str] = Field(min_length=2, max_length=4)
    source_label: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def readable_steps(self) -> "FlowDiagramSpec":
        if any(not step.strip() or len(step) > 32 for step in self.steps):
            raise ValueError("Flow steps must be short, nonempty labels")
        if any(abs(frame.x - 0.5) > 0.01 or abs(frame.y - 0.5) > 0.01
               or not 0.75 <= frame.scale <= 1.05 for frame in self.keyframes):
            raise ValueError("Flow diagram must remain centered inside the safe area")
        return self


class MouthCue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    viseme: Literal["closed", "open", "round", "smile"]


class CharacterDialogueSpec(OverlaySpec):
    text: str = Field(min_length=1, max_length=100)
    character_id: Literal["migo_v1", "luma_v1"]
    expression: Literal["neutral", "happy", "skeptical", "surprised"]
    pose: Literal["idle", "point", "shrug"]
    mouth_cues: list[MouthCue] = Field(min_length=1, max_length=64)
    partner_character_id: Literal["migo_v1", "luma_v1"] | None = None
    partner_text: str | None = Field(default=None, max_length=80)
    partner_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    partner_expression: Literal["neutral", "happy", "skeptical", "surprised"] | None = None
    partner_pose: Literal["idle", "point", "shrug"] | None = None
    partner_mouth_cues: list[MouthCue] | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def safe_character(self) -> "CharacterDialogueSpec":
        if any(abs(frame.x - 0.5) > 0.01 or abs(frame.y - 0.5) > 0.01
               or not 0.75 <= frame.scale <= 1.05 for frame in self.keyframes):
            raise ValueError("Character must remain centered inside the safe area")
        partner_fields = (self.partner_text, self.partner_color, self.partner_expression,
                          self.partner_pose, self.partner_mouth_cues)
        if self.partner_character_id is None:
            if any(value is not None for value in partner_fields):
                raise ValueError("Partner fields require a partner character")
        elif (self.partner_character_id == self.character_id
              or any(value is None for value in partner_fields)
              or not self.partner_text or not self.partner_text.strip()
              or len(self.text) > 80):
            raise ValueError("A pair needs two distinct rigs and complete, short dialogue")
        return self


def validate_overlay(
    item: TimelineItem,
) -> OverlaySpec | MotionCardSpec | FlowDiagramSpec | CharacterDialogueSpec:
    if (
        item.preset not in {"kinetic_title_v1", "motion_card_v1", "flow_path_v1",
                            "character_dialogue_v1"}
        or item.source_asset_id is not None
        or item.source_in_ms is not None or item.speed != 1 or item.z_index < 1
    ):
        raise ValueError(
            "Only local kinetic text, motion cards, flow diagrams or "
            "character dialogue are supported on caption tracks"
        )
    schema = {"kinetic_title_v1": OverlaySpec, "motion_card_v1": MotionCardSpec,
              "flow_path_v1": FlowDiagramSpec,
              "character_dialogue_v1": CharacterDialogueSpec}[item.preset]
    spec = schema.model_validate(item.params)
    if item.preset == "motion_card_v1" and item.duration_ms < 2500:
        raise ValueError("Motion cards need at least 2.5 seconds to read")
    if item.preset == "flow_path_v1" and item.duration_ms < 3000:
        raise ValueError("Flow diagrams need at least 3 seconds to read")
    if item.preset == "character_dialogue_v1":
        if item.duration_ms < 1500:
            raise ValueError("Character dialogue needs at least 1.5 seconds")
        for cues in (spec.mouth_cues, spec.partner_mouth_cues or []):
            if any(cue.end_ms - cue.start_ms < 50 or cue.end_ms > item.duration_ms
                   for cue in cues) or any(
                left.end_ms > right.start_ms for left, right in zip(cues, cues[1:], strict=False)
            ):
                raise ValueError("Mouth cues must be ordered, non-overlapping and within the scene")
    times = [frame.at_ms for frame in spec.keyframes]
    if (
        times[0] != 0 or times[-1] > item.duration_ms
        or any(right - left < 34 for left, right in zip(times, times[1:], strict=False))
    ):
        raise ValueError("Overlay keyframes must start at zero and increase within the item")
    return spec


class SoundSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gain: float = Field(gt=0, le=1)
    fade_in_ms: int = Field(default=0, ge=0)
    fade_out_ms: int = Field(default=0, ge=0)
    loop: bool = False


def validate_sound(item: TimelineItem) -> SoundSpec:
    if (
        item.preset != "sound_v1" or not item.source_asset_id
        or item.speed != 1 or item.z_index != 0
    ):
        raise ValueError("Only local sound assets are supported on audio tracks")
    spec = SoundSpec.model_validate(item.params)
    if spec.fade_in_ms + spec.fade_out_ms > item.duration_ms:
        raise ValueError("Sound fades exceed the item duration")
    if spec.loop and item.source_in_ms is not None:
        raise ValueError("Looped sound does not support a source trim")
    return spec


class VideoLayerSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    focus_x: float = Field(ge=0, le=1)
    focus_y: float = Field(ge=0, le=1)
    opacity: float = Field(gt=0, le=1)


def validate_video_layer(item: TimelineItem) -> VideoLayerSpec:
    if (
        item.preset != "video_overlay_v1" or not item.source_asset_id
        or item.source_in_ms is None or item.source_out_ms is None
        or item.speed != 1 or item.z_index < 1
    ):
        raise ValueError("Video layers need a local MP4, source range and z-index")
    return VideoLayerSpec.model_validate(item.params)


class EDLV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[2] = 2
    revision: int = Field(ge=1)
    canvas: Canvas
    duration_ms: int = Field(gt=0)
    tracks: list[TimelineTrack] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_timeline(self) -> "EDLV2":
        ids: set[str] = set()
        for track in self.tracks:
            if track.id in ids:
                raise ValueError("duplicate track id")
            ids.add(track.id)
            for item in track.items:
                if item.id in ids:
                    raise ValueError("duplicate timeline item id")
                ids.add(item.id)
                if item.start_ms + item.duration_ms > self.duration_ms:
                    raise ValueError("item extends past project duration")
                if track.kind in {"music", "sfx"}:
                    validate_sound(item)
                if track.kind == "caption":
                    validate_overlay(item)
                if track.kind == "video" and track.id != "picture":
                    validate_video_layer(item)
        return self


def from_legacy(
    edl: dict[str, Any], plan: dict[str, Any] | None, *, revision: int = 1
) -> EDLV2:
    """Convert v1 scene timings without changing the stored project."""
    if edl.get("version") != 1:
        raise ValueError("Expected EDL v1")
    format_ = edl.get("format")
    dimensions = {
        "vertical": (1080, 1920), "horizontal": (1920, 1080), "square": (1080, 1080)
    }.get(format_)
    if dimensions is None:
        raise ValueError(f"Unsupported v1 format: {format_}")
    old_tracks = edl.get("tracks") or {}
    videos = old_tracks.get("video") or []
    audio = {item["scene_id"]: item for item in old_tracks.get("audio") or []}
    captions = {item["scene_id"]: item for item in old_tracks.get("captions") or []}
    scenes = {item["id"]: item for item in (plan or {}).get("scenes") or []}
    if not videos:
        raise ValueError("Legacy EDL has no scenes")
    picture: list[TimelineItem] = []
    voice: list[TimelineItem] = []
    graphic: list[TimelineItem] = []
    start = 0
    for old in videos:
        scene_id = str(old["scene_id"])
        duration = round(float(old["duration"]) * 1000)
        if duration <= 0:
            raise ValueError("Legacy scene duration must be positive")
        scene = scenes.get(scene_id, {})
        asset_id = old.get("asset_id") or scene.get("asset_id")
        clip_start = float(old.get("clip_start_seconds") or 0)
        clip_end = old.get("clip_end_seconds")
        source_in = round(clip_start * 1000) if clip_end is not None else None
        source_out = round(float(clip_end) * 1000) if clip_end is not None else None
        picture.append(TimelineItem(
            id=f"picture:{scene_id}", start_ms=start, duration_ms=duration,
            source_asset_id=asset_id, source_in_ms=source_in,
            source_out_ms=source_out, preset="scene_v1",
            params={
                "scene_id": scene_id, "visual_type": old.get("visual_type", "image"),
                "transition": old.get("transition", "cut"), "loop": clip_end is not None,
                "visual_query": scene.get("visual_query", ""),
                "clip_start_seconds": clip_start,
            },
        ))
        voice.append(TimelineItem(
            id=f"voice:{scene_id}", start_ms=start, duration_ms=duration,
            params={"scene_id": scene_id, "text": audio.get(scene_id, {}).get("text", "")},
        ))
        graphic.append(TimelineItem(
            id=f"graphic:{scene_id}", start_ms=start, duration_ms=duration,
            preset="scene_title_v1",
            params={"scene_id": scene_id, "text": captions.get(scene_id, {}).get("text", "")},
        ))
        start += duration
    return EDLV2(
        revision=revision,
        canvas=Canvas(width=dimensions[0], height=dimensions[1], fps_num=30, fps_den=1),
        duration_ms=start,
        tracks=[
            TimelineTrack(id="picture", kind="video", items=picture),
            TimelineTrack(id="narration", kind="voice", items=voice),
            TimelineTrack(id="titles", kind="graphic", items=graphic),
        ],
    )


def to_legacy(edl: EDLV2, format_: str) -> dict[str, Any]:
    """Return v1 only when every edit is supported by the existing renderer."""
    dimensions = {
        "vertical": (1080, 1920), "horizontal": (1920, 1080), "square": (1080, 1080)
    }.get(format_)
    if dimensions != (edl.canvas.width, edl.canvas.height):
        raise ValueError("Canvas does not match project format")
    if (edl.canvas.fps_num, edl.canvas.fps_den) != (30, 1):
        raise ValueError("The v1 renderer only supports 30 fps")
    by_kind = {track.kind: track for track in edl.tracks}
    if len(by_kind) != len(edl.tracks):
        raise ValueError("duplicate track kind is not supported by the v1 renderer")
    if any(track.items for track in edl.tracks if track.kind not in {"video", "voice", "graphic"}):
        raise ValueError("This renderer does not yet support additional tracks")
    if not all(kind in by_kind for kind in ("video", "voice", "graphic")):
        raise ValueError("Picture, voice and title tracks are required")
    pictures = sorted(by_kind["video"].items, key=lambda item: item.start_ms)
    narrations = {item.params.get("scene_id"): item for item in by_kind["voice"].items}
    titles = {item.params.get("scene_id"): item for item in by_kind["graphic"].items}
    result: dict[str, list[dict[str, Any]]] = {"video": [], "audio": [], "captions": []}
    cursor = 0
    scene_ids: set[str] = set()
    for item in pictures:
        scene_id = item.params.get("scene_id")
        if not isinstance(scene_id, str) or item.start_ms != cursor:
            raise ValueError("The v1 renderer requires contiguous ordered scenes")
        if scene_id in scene_ids:
            raise ValueError("Duplicate scene ID")
        scene_ids.add(scene_id)
        narration = narrations.get(scene_id)
        title = titles.get(scene_id)
        if not narration or not title or (
            narration.start_ms != cursor or title.start_ms != cursor
            or narration.duration_ms != item.duration_ms or title.duration_ms != item.duration_ms
        ):
            raise ValueError("The v1 renderer requires aligned voice and title items")
        if item.preset != "scene_v1" or title.preset != "scene_title_v1":
            raise ValueError("Unknown preset cannot be rendered by v1")
        if (
            item.speed != 1 or item.z_index != 0 or title.z_index != 0
            or narration.z_index != 0 or item.params.get("keyframes")
            or title.params.get("keyframes") or narration.params.get("keyframes")
        ):
            raise ValueError("Speed and keyframes require the v2 renderer")
        if set(item.params) - {
            "scene_id", "visual_type", "transition", "loop", "visual_query",
            "clip_start_seconds",
        }:
            raise ValueError("Unsupported picture parameters")
        if set(title.params) - {"scene_id", "text"} or set(narration.params) - {
            "scene_id", "text"
        }:
            raise ValueError("Unsupported title or voice parameters")
        if item.source_asset_id is None and item.source_in_ms is not None:
            raise ValueError("Source trim needs an asset")
        clip_start = (
            item.source_in_ms / 1000 if item.source_in_ms is not None
            else float(item.params.get("clip_start_seconds") or 0)
        )
        clip_end = item.source_out_ms / 1000 if item.source_out_ms is not None else None
        result["video"].append({
            "scene_id": scene_id, "duration": item.duration_ms / 1000,
            "visual_type": item.params.get("visual_type", "image"),
            "transition": item.params.get("transition", "cut"),
            "asset_id": item.source_asset_id,
            "clip_start_seconds": clip_start, "clip_end_seconds": clip_end,
        })
        result["audio"].append({"scene_id": scene_id, "text": narration.params["text"]})
        result["captions"].append({"scene_id": scene_id, "text": title.params["text"]})
        cursor += item.duration_ms
    if (
        cursor != edl.duration_ms
        or len(narrations) != len(pictures)
        or len(titles) != len(pictures)
    ):
        raise ValueError("Every scene must have one voice and one title")
    return {"version": 1, "format": format_, "tracks": result}


def scene_projection(
    edl: EDLV2, format_: str
) -> tuple[dict[str, Any], list[TimelineItem], list[TimelineItem], list[TimelineItem]]:
    """Project scenes to v1 while retaining supported visual and sound layers."""
    overlays = [
        item for track in edl.tracks if track.kind == "caption" for item in track.items
    ]
    sounds = [
        item for track in edl.tracks if track.kind in {"music", "sfx"}
        for item in track.items
    ]
    video_layers = [
        item for track in edl.tracks
        if track.kind == "video" and track.id != "picture"
        for item in track.items
    ]
    base = edl.model_copy(update={
        "tracks": [
            track for track in edl.tracks
            if track.kind not in {"caption", "music", "sfx"}
            and not (track.kind == "video" and track.id != "picture")
        ],
    })
    return to_legacy(base, format_), overlays, sounds, video_layers
