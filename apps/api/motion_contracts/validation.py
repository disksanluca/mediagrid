"""Semantic validators and read-only binding to the existing storyboard/EDL v2."""

from collections import Counter
from collections.abc import Mapping

from apps.api.creative.contracts import CreativeDNA, CreativeStoryboard
from apps.api.edl_v2 import EDLV2

from .models import (
    AssetBinding,
    Contract,
    MotionComposition,
    MotionRecipe,
    MotionScene,
    PathGeometry,
)


def unique(values, label):
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {label}")


def frame_at(ms: int) -> int:
    """Absolute 30-fps boundaries, integer round-half-up (no accumulated rounding)."""
    return (ms * 30 + 500) // 1000


def resolve_time(time, cues):
    if time.kind == "ms":
        return time.at_ms
    if time.cue_ref not in cues:
        raise ValueError(f"Unknown cue: {time.cue_ref}")
    return cues[time.cue_ref].at_ms + time.offset_ms


def animation_times(animation, cues):
    times = [resolve_time(k.time, cues) for k in animation.keyframes]
    if any(t < 0 or t > 30000 for t in times) or any(
        b <= a for a, b in zip(times, times[1:], strict=False)
    ):
        raise ValueError("Keyframe times must increase within [0, 30000]")
    return times


def z_range(transform):
    values = [transform.position[2]]
    values.extend(k.value[2] for a in transform.animations
                  if a.property == "position" for k in a.keyframes)
    return min(values), max(values)


def complexity(scene):
    vertices = 0
    for node in scene.nodes:
        geometry = getattr(getattr(node, "params", None), "geometry", None)
        if isinstance(geometry, PathGeometry):
            vertices += len(geometry.points)
    return {
        "nodes": len(scene.nodes) + sum(n.params.count for n in scene.nodes
                                       if n.type == "particle"),
        "vertices": vertices,
        "keyframes": sum(len(a.keyframes) for n in [*scene.nodes, scene.camera]
                         for a in n.animations),
        "cues": len(scene.cues),
    }


def parents(node, nodes):
    chain = [node]
    seen = {node.id}
    while chain[-1].parent_id is not None:
        parent = nodes.get(chain[-1].parent_id)
        if parent is None or parent.type != "group":
            raise ValueError("Parent must reference an existing group")
        if parent.id in seen:
            raise ValueError("Hierarchy cycle")
        if parent.space != node.space:
            raise ValueError("Parent and child must use the same coordinate space")
        seen.add(parent.id)
        chain.append(parent)
        if len(chain) > 6:
            raise ValueError("Hierarchy exceeds depth 6")
    return chain


def validate_graph(scene: MotionScene):
    unique([n.id for n in scene.nodes], "node ID")
    unique([c.id for c in scene.cues], "cue ID")
    nodes = {n.id: n for n in scene.nodes}
    cues = {c.id: c for c in scene.cues}
    masks = {}
    for node in scene.nodes:
        chain = parents(node, nodes)
        if node.space == "world":
            near = scene.camera.focal_length + sum(z_range(n)[0] for n in chain)
            if near - z_range(scene.camera)[1] <= 32:
                raise ValueError("Camera near-plane crossing or unsafe depth range")
        if node.type == "mask":
            target = nodes.get(node.params.target_id)
            if target is None or target.type != "group" or (
                target.parent_id != node.parent_id or target.space != node.space
            ):
                raise ValueError("Mask target must be a sibling group in the same space")
            if target.id in masks:
                raise ValueError("Only one mask may target a group")
            masks[target.id] = node.id
        if node.type == "path_follower":
            path = nodes.get(node.params.path_ref)
            if path is None or path.type != "shape" or (
                not isinstance(path.params.geometry, PathGeometry)
                or path.parent_id != node.parent_id or path.space != node.space
            ):
                raise ValueError("Follower needs a sibling shape path in the same space")
        allowed = {"position", "scale", "rotate_z", "opacity"}
        if node.type == "shape":
            allowed.add("draw_progress")
        if node.type in {"mask", "path_follower"}:
            allowed.add("progress")
        unique([a.property for a in node.animations], "animated property")
        if any(a.property not in allowed for a in node.animations):
            raise ValueError("Animation property is not supported by node type")
        for animation in node.animations:
            animation_times(animation, cues)
        if node.active_ms is not None and node.active_ms[1] <= node.active_ms[0]:
            raise ValueError("Active interval must be positive")
    for node in scene.nodes:
        if sum(p.id in masks for p in parents(node, nodes)) > 2:
            raise ValueError("Mask nesting exceeds 2")
    unique([a.property for a in scene.camera.animations], "camera property")
    for animation in scene.camera.animations:
        animation_times(animation, cues)
    budget = complexity(scene)
    if budget["nodes"] > 128 or sum(
        n.params.count for n in scene.nodes if n.type == "particle"
    ) > 64:
        raise ValueError("Expanded nodes/particles exceed scene budget")


def active_interval(node, nodes, duration_ms):
    start, end = 0, duration_ms
    for ancestor in reversed(parents(node, nodes)):
        if ancestor.active_ms is not None:
            a, b = ancestor.active_ms
            if a < start or b > end:
                raise ValueError("Child active interval exceeds parent/shot")
            start, end = a, b
    return start, end


def peak_overlap(intervals):
    events = [(start, 1) for start, _ in intervals] + [(end, -1) for _, end in intervals]
    total = peak = 0
    for _, delta in sorted(events):  # End before start: half-open intervals.
        total += delta
        peak = max(peak, total)
    return peak


def validate_scene_bounds(scene, duration_ms, canvas, start_ms=0, *, quantize=True):
    at = frame_at if quantize else lambda ms: ms
    if duration_ms <= 0 or (quantize and at(start_ms + duration_ms) - at(start_ms) < 2):
        raise ValueError("Shot must contain at least two frames")
    safe = scene.safe_area
    if safe.left + safe.right >= canvas.width or safe.top + safe.bottom >= canvas.height:
        raise ValueError("Safe area consumes canvas")
    cues = {c.id: c for c in scene.cues}
    nodes = {n.id: n for n in scene.nodes}
    media = {"image": [], "video": [], "light_sweep": [], "audio": []}
    for cue in scene.cues:
        if cue.at_ms >= duration_ms or at(start_ms+cue.at_ms) >= at(
            start_ms+duration_ms
        ):
            raise ValueError("Cue outside shot frames")
        if cue.sound:
            end = cue.at_ms + cue.sound.duration_ms
            if end > duration_ms:
                raise ValueError("Sound cue exceeds shot")
            if at(start_ms+end) <= at(start_ms+cue.at_ms):
                raise ValueError("Sound cue collapses to zero frames")
            media["audio"].append((at(start_ms+cue.at_ms), at(start_ms+end)))
    for node in [*scene.nodes, scene.camera]:
        interval = active_interval(node, nodes, duration_ms) if node is not scene.camera else (
            0, duration_ms
        )
        if at(start_ms+interval[0]) >= at(start_ms+interval[1]):
            raise ValueError("Active interval collapses to zero frames")
        for animation in node.animations:
            times = animation_times(animation, cues)
            if times[0] < interval[0] or times[-1] > interval[1]:
                raise ValueError("Keyframes outside active interval")
            frames = [at(start_ms+t) for t in times]
            if any(b <= a for a, b in zip(frames, frames[1:], strict=False)):
                raise ValueError("Keyframes collapse to the same absolute frame")
        if getattr(node, "type", None) in media:
            media[node.type].append(tuple(at(start_ms+t) for t in interval))
    for kind, limit in (("image", 4), ("video", 2), ("light_sweep", 2), ("audio", 8)):
        if peak_overlap(media[kind]) > limit:
            raise ValueError(f"Concurrent {kind} limit exceeded")


def slots_used(scene):
    result = []
    for node in scene.nodes:
        if node.type in {"image", "video"}:
            result.append((node.params.asset_binding, node.type))
    for cue in scene.cues:
        if cue.sound:
            result.append((cue.sound.asset_binding, "audio"))
    return result


def validate_slots(graphs, slots):
    used = set()
    for graph in graphs:
        for slot, kind in slots_used(graph):
            if slots.get(slot) != kind:
                raise ValueError(f"Missing asset slot or incompatible kind: {slot}")
            used.add(slot)
    if set(slots) != used:
        raise ValueError("Unused asset slots are forbidden")


def total_budget(graphs):
    total = Counter()
    for graph in graphs:
        total.update(complexity(graph))
    for name, limit in (("nodes", 512), ("vertices", 4096), ("keyframes", 8192), ("cues", 64)):
        if total[name] > limit:
            raise ValueError(f"Composition {name} budget exceeded")
    return dict(total)


def validate_envelope(composition: MotionComposition):
    unique([s.shot_id for s in composition.scenes], "shot binding")
    total_budget([s.graph for s in composition.scenes])
    validate_slots([s.graph for s in composition.scenes],
                   {k: v.kind for k, v in composition.asset_bindings.items()})
    if sum(a.byte_size for a in composition.asset_bindings.values()) > 256*1024*1024:
        raise ValueError("Asset byte budget exceeds 256 MiB")
    identities = {}
    for asset in composition.asset_bindings.values():
        if asset.asset_id in identities and identities[asset.asset_id] != asset:
            raise ValueError("Conflicting metadata/hash for the same asset")
        identities[asset.asset_id] = asset
    # The actual per-shot duration comes from EDL at binding; this is an outer bound.
    for scene in composition.scenes:
        validate_scene_bounds(scene.graph, composition.expected.duration_ms,
                              composition.expected.canvas, quantize=False)


def validate_recipe(recipe: MotionRecipe):
    unique([s.shot_slot for s in recipe.scenes], "recipe shot slot")
    duration = sum(s.required_duration_ms for s in recipe.scenes)
    if not 3000 <= duration <= 30000:
        raise ValueError("Recipe duration assertions must total 3..30 seconds")
    total_budget([s.graph for s in recipe.scenes])
    validate_slots([s.graph for s in recipe.scenes], recipe.asset_slots)
    cursor = 0
    for scene in recipe.scenes:
        validate_scene_bounds(scene.graph, scene.required_duration_ms, recipe.canvas, cursor)
        cursor += scene.required_duration_ms


def bindings_in(value):
    if isinstance(value, Contract):
        if getattr(value, "kind", "") in {"dna_font", "dna_palette", "shot_field",
                                         "approved_claim_field"}:
            yield value
        else:
            for field in type(value).model_fields:
                yield from bindings_in(getattr(value, field))
    elif isinstance(value, list):
        for child in value:
            yield from bindings_in(child)


def validate_binding(
    composition: MotionComposition, *, edl: EDLV2, storyboard: CreativeStoryboard,
    dna: CreativeDNA, project_id: str, storyboard_revision: int, snapshot_sha256: str,
    available_assets: Mapping[str, AssetBinding],
    approved_claims: Mapping[str, Mapping[str, str]], recipe: MotionRecipe,
) -> dict:
    """Read-only consistency check. Caller must obtain trusted state/rights; not approval."""
    composition = MotionComposition.model_validate(composition.model_dump(mode="json"))
    from .registry import verify_recipe_binding
    verify_recipe_binding(composition, recipe)
    expected = composition.expected
    if (composition.project_id, expected.storyboard_revision, expected.snapshot_sha256) != (
        project_id, storyboard_revision, snapshot_sha256
    ):
        raise ValueError("Stale project/revision/snapshot binding")
    if edl.canvas.model_dump() != expected.canvas.model_dump() or (
        edl.duration_ms != expected.duration_ms or storyboard.duration_ms != edl.duration_ms
        or storyboard.fps != 30
    ):
        raise ValueError("Canvas/FPS/duration differs from approved EDL/storyboard")
    pictures = [t for t in edl.tracks if t.id == "picture" and t.kind == "video"]
    if len(pictures) != 1:
        raise ValueError("Existing EDL picture track required")
    shots = storyboard.shots
    if [s.shot_id for s in composition.scenes] != [s.id for s in shots]:
        raise ValueError("Scene bindings must match approved shot order exactly")
    picture = sorted(pictures[0].items, key=lambda item: item.start_ms)
    if [(p.params.get("scene_id"), p.start_ms, p.duration_ms) for p in picture] != [
        (s.id, s.start_ms, s.duration_ms) for s in shots
    ]:
        raise ValueError("EDL picture timings differ from storyboard")
    for asset in composition.asset_bindings.values():
        if available_assets.get(asset.asset_id) != asset:
            raise ValueError("Asset missing or declared metadata/hash differs")
    reports = []
    for scene, shot in zip(composition.scenes, shots, strict=True):
        template = recipe.scenes[len(reports)]
        if shot.duration_ms != template.required_duration_ms:
            raise ValueError("Shot duration differs from recipe assertion")
        validate_scene_bounds(scene.graph, shot.duration_ms, expected.canvas, shot.start_ms)
        nodes = {n.id: n for n in scene.graph.nodes}
        for binding in bindings_in(scene.graph):
            if binding.kind == "dna_palette" and binding.index >= len(dna.palette):
                raise ValueError("Palette binding outside Creative DNA")
            if binding.kind == "approved_claim_field" and (
                binding.claim_id not in shot.claim_ids
                or binding.claim_id not in approved_claims
            ):
                raise ValueError("Claim binding is not approved for this shot")
        for node in scene.graph.nodes:
            if node.type == "text":
                binding = node.params.text
                text = shot.on_screen_text if binding.kind == "shot_field" else (
                    approved_claims[binding.claim_id].get(binding.field)
                )
                if not isinstance(text, str) or not text.strip() or len(text) > 240 or (
                    len(text.splitlines()) > node.params.max_lines
                ):
                    raise ValueError("Resolved text missing or exceeds contract limits")
            if node.type in {"image", "video"}:
                asset = composition.asset_bindings[node.params.asset_binding]
                if asset.asset_id not in shot.asset_ids:
                    raise ValueError("Visual asset is not in the approved shot")
                if node.type == "video":
                    a, b = active_interval(node, nodes, shot.duration_ms)
                    if node.params.source_in_ms + b-a > asset.duration_ms:
                        raise ValueError("Video source trim exceeds asset duration")
        for cue in scene.graph.cues:
            if cue.sound:
                asset = composition.asset_bindings[cue.sound.asset_binding]
                if asset.asset_id not in shot.asset_ids:
                    raise ValueError("Audio asset is not in the approved shot")
                if cue.sound.source_in_ms + cue.sound.duration_ms > asset.duration_ms:
                    raise ValueError("Sound trim exceeds source asset duration")
        reports.append({
            "shot_id": shot.id,
            "start_frame": frame_at(shot.start_ms),
            "end_frame": frame_at(shot.start_ms+shot.duration_ms),
            "cues": [{
                "id": c.id, "absolute_frame": frame_at(shot.start_ms+c.at_ms),
                # Integer thirds of a millisecond avoids unverifiable float rounding.
                "rounding_error_ms_times_3": (
                    frame_at(shot.start_ms+c.at_ms)*100 - (shot.start_ms+c.at_ms)*3
                ),
            } for c in scene.graph.cues],
        })
    return {"status": "CONTRACT_VALID", "render_supported": False, "shots": reports,
            "complexity": total_budget([s.graph for s in composition.scenes])}
