"""M4.A contracts: synthetic data only; no renderer, installed database or external I/O."""

import hashlib
import json
import shutil

import pytest
from pydantic import ValidationError

from apps.api.creative.contracts import CreativeDNA, CreativeStoryboard
from apps.api.edl_v2 import EDLV2, TimelineItem, from_legacy, to_legacy, validate_sound
from apps.api.motion_contracts.canonical import (
    MAX_JSON_BYTES,
    canonical_bytes,
    contract_sha256,
    read_json,
)
from apps.api.motion_contracts.models import (
    MotionComposition,
    MotionRecipe,
    MotionScene,
    VideoParams,
)
from apps.api.motion_contracts.registry import (
    REGISTRY_ROOT,
    RegistryIndex,
    load_recipe,
    recipe_digest,
    verify_recipe_binding,
)
from apps.api.motion_contracts.validation import frame_at, validate_binding, validate_scene_bounds
from scripts.generate_motion_contracts import OUTPUT, artifacts, ts_type

FIXTURES = REGISTRY_ROOT.parent / "fixtures"


@pytest.fixture(autouse=True)
def clean_database():
    # Override the integration suite's DB-reset fixture: these tests are pure contracts.
    yield


def document(name, file="composition"):
    return read_json((FIXTURES / name / f"{file}.json").read_bytes())


def fixture(name="sports"):
    comp = MotionComposition.model_validate(document(name))
    context = document(name, "context")
    context.update(
        edl=EDLV2.model_validate(document(name, "edl_v2")),
        storyboard=CreativeStoryboard.model_validate(document(name, "storyboard")),
        dna=CreativeDNA.model_validate(document(name, "dna")),
        available_assets={a.asset_id: a for a in comp.asset_bindings.values()},
        recipe=load_recipe(comp.recipe.id, comp.recipe.version),
    )
    return comp, context


def graph(nodes=None, **kwargs):
    return MotionScene.model_validate({"schema_version": "motion_scene_v1",
        "nodes": nodes or [{"id": "g", "type": "group"}], **kwargs})


def animation(times=(0, 1000), prop="opacity"):
    return {"property": prop, "keyframes": [
        {"time": {"kind": "ms", "at_ms": t}, "value": 1} for t in times
    ]}


@pytest.mark.parametrize("name", ["sports", "music", "geo"])
def test_fixtures_bind_without_altering_legacy_edl_or_claiming_render(name):
    comp, context = fixture(name)
    edl = context["edl"]
    before = canonical_bytes(edl)
    fmt = {"sports": "vertical", "music": "square", "geo": "horizontal"}[name]
    legacy = to_legacy(edl, fmt)
    report = validate_binding(comp, **context)
    assert report["status"] == "CONTRACT_VALID" and report["render_supported"] is False
    assert report["shots"][0]["end_frame"] == comp.expected.duration_ms * 30 // 1000
    assert canonical_bytes(edl) == before
    assert to_legacy(edl, fmt) == legacy
    assert load_recipe(comp.recipe.id, comp.recipe.version).sha256 == comp.recipe.sha256


def test_examples_have_distinct_structure_not_only_text_or_palette():
    signatures = []
    for name in ("sports", "music", "geo"):
        comp, _ = fixture(name)
        signatures.append(tuple(n.type for n in comp.scenes[0].graph.nodes))
    assert len(set(signatures)) == 3
    assert "mask" in signatures[0] and "image" in signatures[1]
    assert "path_follower" in signatures[2]


@pytest.mark.parametrize("path,value", [
    (("schema_version",), "motion_composition_v2"),
    (("expected", "storyboard_revision"), True),
    (("expected", "duration_ms"), "12000"),
    (("expected", "duration_ms"), 30001),
    (("expected", "canvas", "fps_num"), 60),
    (("expected", "canvas", "fps_den"), True),
    (("expected", "canvas", "width"), 720),
    (("expected", "snapshot_sha256"), "not-a-hash"),
    (("recipe", "id"), "../remote.py"),
    (("recipe", "version"), "01.0.0"),
    (("asset_bindings", "score", "asset_id"), "https://host/track.wav"),
    (("asset_bindings", "score", "sha256"), "F"*64),
    (("asset_bindings", "score", "byte_size"), 128*1024*1024+1),
    (("asset_bindings", "score", "channels"), 8),
])
def test_strict_envelope_rejects_coercion_and_unsupported_values(path, value):
    data = document("sports")
    cursor = data
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    with pytest.raises(ValidationError):
        MotionComposition.model_validate(data)


@pytest.mark.parametrize("node", [
    {"id": "g", "type": "eval", "code": "process.exit()"},
    {"id": "g", "type": "group", "style": {"background": "url(https://remote)"}},
    {"id": "g", "type": "group", "onClick": "fetch('/publish')"},
    {"id": "g", "type": "group", "position": [0, 0, float("nan")]},
    {"id": "g", "type": "group", "opacity": float("inf")},
    {"id": "g", "type": "group", "opacity": True},
    {"id": "g", "type": "group", "scale": [0, 1]},
    {"id": "g", "type": "group", "position": [0, 0]},
    {"id": "g", "type": "group", "position": [0, 0, 4001]},
    {"id": "g", "type": "group", "active_ms": [100, 10]},
    {"id": "g", "type": "group", "opacity": 0.0000001},
    {"id": "g", "type": "group", "animations": [animation(prop="progress")]},
])
def test_untrusted_nodes_are_closed_data(node):
    with pytest.raises(ValueError):
        graph([node])


@pytest.mark.parametrize("nodes,match", [
    ([{"id": "a", "type": "group", "parent_id": "b"},
      {"id": "b", "type": "group", "parent_id": "a"}], "cycle"),
    ([{"id": "a", "type": "group", "parent_id": "absent"}], "Parent"),
    ([{"id": "a", "type": "group"}, {"id": "a", "type": "group"}], "Duplicate"),
    ([{"id": f"g{i}", "type": "group", "parent_id": f"g{i-1}" if i else None}
      for i in range(7)], "depth"),
    ([{"id": "a", "type": "group", "space": "screen"},
      {"id": "b", "type": "group", "parent_id": "a"}], "coordinate space"),
])
def test_hierarchy_errors(nodes, match):
    with pytest.raises(ValueError, match=match):
        graph(nodes)


def test_mask_and_path_references_are_typed_and_local():
    for name, index, field in (("sports", 4, "target_id"), ("geo", 3, "path_ref")):
        data = document(name)["scenes"][0]["graph"]
        data["nodes"][index]["params"][field] = "not-present"
        with pytest.raises(ValueError):
            MotionScene.model_validate(data)
    data = document("geo")["scenes"][0]["graph"]
    data["nodes"][3]["params"]["path_ref"] = "heading"
    with pytest.raises(ValueError, match="path"):
        MotionScene.model_validate(data)


def test_nested_masks_are_bounded():
    nodes = [{"id": f"g{i}", "type": "group", "parent_id": f"g{i-1}" if i else None}
             for i in range(3)]
    nodes += [{"id": f"m{i}", "type": "mask", "parent_id": f"g{i-1}" if i else None,
               "params": {"target_id": f"g{i}", "geometry": {
                   "kind": "rect", "width": 100, "height": 100}}} for i in range(3)]
    with pytest.raises(ValueError, match="Mask nesting"):
        graph(nodes)


def test_camera_near_plane_considers_animated_ancestors():
    nodes = [{"id": "p", "type": "group", "position": [0, 0, -500]},
             {"id": "c", "type": "group", "parent_id": "p", "position": [0, 0, -500]}]
    with pytest.raises(ValueError, match="near-plane"):
        graph(nodes, camera={"position": [0, 0, 300]})
    nodes[0]["position"] = [0, 0, 0]
    nodes[0]["animations"] = [{"property": "position", "keyframes": [
        {"time": {"kind": "ms", "at_ms": 0}, "value": [0, 0, 0]},
        {"time": {"kind": "ms", "at_ms": 1000}, "value": [0, 0, -600]},
    ]}]
    with pytest.raises(ValueError, match="near-plane"):
        graph(nodes, camera={"position": [0, 0, 300]})


@pytest.mark.parametrize("times", [(100, 0), (0, 0), (-1, 100), (0, 30001)])
def test_keyframe_order_and_bounds(times):
    with pytest.raises(ValueError):
        graph([{"id": "g", "type": "group", "animations": [animation(times)]}])


def test_cue_reference_and_exclusive_time_variants():
    data = {"id": "g", "type": "group", "animations": [animation()]}
    frame = data["animations"][0]["keyframes"][1]
    frame["time"] = {"kind": "cue", "cue_ref": "hit", "offset_ms": -10}
    with pytest.raises(ValueError, match="Unknown cue"):
        graph([data])
    with pytest.raises(ValueError, match="increase"):
        graph([data], cues=[{"id": "hit", "at_ms": 5}])
    frame["time"]["offset_ms"] = 0
    frame["time"]["at_ms"] = 1000
    with pytest.raises(ValueError):
        graph([data], cues=[{"id": "hit", "at_ms": 1000}])


def test_absolute_rounding_not_independent_local_rounding():
    scene = graph([{"id": "g", "type": "group", "animations": [animation((0, 1))]}])
    canvas = fixture()[0].expected.canvas
    with pytest.raises(ValueError, match="same absolute frame"):
        validate_scene_bounds(scene, 3000, canvas)
    validate_scene_bounds(scene, 2984, canvas, start_ms=16)
    assert frame_at(16) == 0 and frame_at(17) == 1
    assert frame_at(1001) + (frame_at(3000)-frame_at(1001)) == 90


@pytest.mark.parametrize("cue", [
    {"id": "last", "at_ms": 2999},
    {"id": "late", "at_ms": 3000},
    {"id": "sound", "at_ms": 2000, "sound": {"asset_binding": "score", "duration_ms": 1001}},
    {"id": "tiny", "at_ms": 1000, "sound": {"asset_binding": "score", "duration_ms": 1}},
])
def test_cues_cannot_escape_or_collapse(cue):
    scene = graph(cues=[cue])
    with pytest.raises(ValueError):
        validate_scene_bounds(scene, 3000, fixture()[0].expected.canvas)


def test_duplicate_cues_properties_and_invalid_easing():
    with pytest.raises(ValueError, match="Duplicate"):
        graph(cues=[{"id": "hit", "at_ms": 0}, {"id": "hit", "at_ms": 500}])
    node = {"id": "g", "type": "group", "animations": [animation(), animation()]}
    with pytest.raises(ValueError, match="Duplicate"):
        graph([node])
    node["animations"] = [animation()]
    node["animations"][0]["keyframes"][0]["easing"] = {
        "kind": "cubic_bezier", "controls": [0, -2, 1, 2]}
    with pytest.raises(ValueError):
        graph([node])


def test_particle_expansion_and_geometry_budgets():
    particle = {"id": "p", "type": "particle", "params": {
        "seed": 42, "count": 64, "velocity": [0, 1], "radius": 2,
        "fill": {"kind": "dna_palette", "index": 1}}}
    with pytest.raises(ValueError, match="Expanded"):
        graph([particle]+[{"id": f"g{i}", "type": "group"} for i in range(64)])
    data = document("sports")
    geometry = {"kind": "polygon", "points": [[i, 0] for i in range(500)]}
    data["scenes"][0]["graph"]["nodes"] = [
        {"id": f"s{i}", "type": "shape", "params": {
            "geometry": geometry, "fill": {"index": 1}}} for i in range(9)]
    with pytest.raises(ValueError, match="vertices"):
        MotionComposition.model_validate(data)


def test_media_concurrency_uses_inherited_active_intervals():
    nodes = [{"id": f"i{i}", "type": "image", "params": {
        "asset_binding": "cover", "width": 100, "height": 100}} for i in range(5)]
    canvas = fixture()[0].expected.canvas
    with pytest.raises(ValueError, match="Concurrent image"):
        validate_scene_bounds(graph(nodes), 3000, canvas)
    nodes[-1]["active_ms"] = [2000, 3000]
    for node in nodes[:-1]:
        node["active_ms"] = [0, 2000]
    validate_scene_bounds(graph(nodes), 3000, canvas)
    nodes[0]["parent_id"] = "parent"
    nodes.append({"id": "parent", "type": "group", "active_ms": [1000, 3000]})
    with pytest.raises(ValueError, match="parent/shot"):
        validate_scene_bounds(graph(nodes), 3000, canvas)


def test_asset_kinds_unused_slots_dimensions_and_total_bytes():
    data = document("music")
    data["asset_bindings"]["cover"]["width"] = 4097
    with pytest.raises(ValueError):
        MotionComposition.model_validate(data)
    data = document("sports")
    data["asset_bindings"]["unused"] = data["asset_bindings"]["score"]
    with pytest.raises(ValueError, match="Unused"):
        MotionComposition.model_validate(data)
    data = document("music")
    data["scenes"][0]["graph"]["nodes"][3]["params"]["asset_binding"] = "score"
    with pytest.raises(ValueError, match="incompatible kind"):
        MotionComposition.model_validate(data)
    data = document("sports")
    for i in range(3):
        name = f"audio{i}"
        data["asset_bindings"][name] = {
            **data["asset_bindings"]["score"], "asset_id": name, "byte_size": 128*1024*1024}
        data["scenes"][0]["graph"]["cues"].append({
            "id": name, "at_ms": 0, "sound": {"asset_binding": name, "duration_ms": 1000}})
    with pytest.raises(ValueError, match="byte budget"):
        MotionComposition.model_validate(data)


@pytest.mark.parametrize("field,value", [
    ("project_id", "another-project"),
    ("storyboard_revision", 2),
    ("snapshot_sha256", "f"*64),
    ("available_assets", {}),
])
def test_stale_or_missing_trusted_dependencies(field, value):
    comp, context = fixture()
    context[field] = value
    with pytest.raises(ValueError):
        validate_binding(comp, **context)


def test_asset_hash_tamper_and_claim_approval_are_detected():
    comp, context = fixture()
    asset = next(iter(comp.asset_bindings.values()))
    context["available_assets"][asset.asset_id] = asset.model_copy(update={"sha256": "f"*64})
    with pytest.raises(ValueError, match="Asset missing"):
        validate_binding(comp, **context)
    comp, context = fixture("geo")
    context["approved_claims"] = {}
    with pytest.raises(ValueError, match="Claim binding"):
        validate_binding(comp, **context)


def test_edl_dna_and_shot_bindings_are_assertions_not_overrides():
    comp, context = fixture()
    context["edl"] = context["edl"].model_copy(update={"duration_ms": 13000})
    with pytest.raises(ValueError, match="duration"):
        validate_binding(comp, **context)
    comp, context = fixture()
    context["dna"] = context["dna"].model_copy(update={"palette": ["#000000", "#FFFFFF"]})
    with pytest.raises(ValueError, match="Palette"):
        validate_binding(comp, **context)
    comp, context = fixture()
    context["storyboard"].shots[0].asset_ids.clear()
    with pytest.raises(ValueError, match="approved shot"):
        validate_binding(comp, **context)


def test_render_preset_remains_unsupported_until_m4_b():
    data = document("sports", "edl_v2")
    data["tracks"].append({"id": "motion", "kind": "caption", "items": [{
        "id": "not-renderable", "start_ms": 0, "duration_ms": 12000,
        "preset": "motion_scene_v1", "z_index": 1,
        "params": document("sports")["scenes"][0]["graph"]}]})
    with pytest.raises(ValueError, match="Only local kinetic"):
        EDLV2.model_validate(data)


@pytest.mark.parametrize("payload", [
    b'{"id":"one","id":"two"}',
    b'{"number":NaN}',
    b'{"number":Infinity}',
    b'{"number":1e999}',
    b'{"x":1e-8}',
    b'{"x":9007199254740992}',
    b'{"x":'+b'9'*500+b'}',
    b'{"x":"\\ud800"}',
    b'[]',
    b' '*(MAX_JSON_BYTES+1),
    b'{"x":'+b'['*30+b'0'+b']'*30+b'}',
], ids=["duplicate", "nan", "infinity", "overflow", "precision", "unsafe-int", "huge-int",
        "surrogate", "root-array", "size-limit", "depth-limit"])
def test_raw_json_security_boundary(payload):
    with pytest.raises(ValueError):
        read_json(payload)


def test_canonical_numeric_unicode_and_default_vectors():
    value = {"z": [-0.0, 1.0, 1.25], "a": "É"}
    expected = '{"a":"É","z":[0,1,1.25]}'.encode()
    assert canonical_bytes(value) == expected
    assert contract_sha256(value) == hashlib.sha256(expected).hexdigest()
    assert canonical_bytes({"x": 1}) == canonical_bytes({"x": 1.0})
    minimal = graph()
    expanded = MotionScene.model_validate(minimal.model_dump(mode="json"))
    assert canonical_bytes(minimal) == canonical_bytes(expanded)
    assert contract_sha256([1, 2]) != contract_sha256([2, 1])
    assert contract_sha256({"a": 1, "b": 2}) == contract_sha256({"b": 2, "a": 1})


def test_recipe_registry_detects_tampering_and_unknown_versions(tmp_path):
    root = tmp_path / "recipes"
    shutil.copytree(REGISTRY_ROOT, root)
    recipe = load_recipe("sports.depth-impact", "1.0.0", root=root)
    file = root / f"{recipe.id}.{recipe.version}.json"
    data = read_json(file.read_bytes())
    data["scenes"][0]["graph"]["nodes"][0]["opacity"] = 0.5
    file.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        load_recipe(recipe.id, recipe.version, root=root)
    with pytest.raises(ValueError, match="registered"):
        load_recipe(recipe.id, "2.0.0", root=root)
    with pytest.raises(ValueError):
        load_recipe("../escape", "1.0.0", root=root)


def test_recipe_binding_rejects_arbitrary_graph_and_mutated_model_container():
    comp, context = fixture()
    data = comp.model_dump(mode="json")
    data["scenes"][0]["graph"]["nodes"][0]["opacity"] = 0.3
    modified = MotionComposition.model_validate(data)
    with pytest.raises(ValueError, match="differs from registered recipe"):
        verify_recipe_binding(modified, context["recipe"])
    context["recipe"].scenes[0].graph.nodes[0].position[0] = 400
    with pytest.raises(ValueError, match="hash"):
        verify_recipe_binding(comp, context["recipe"])


def test_generated_contracts_are_fresh_and_closed():
    for name, expected in artifacts().items():
        assert (OUTPUT / name).read_text(encoding="utf-8") == expected, name
    schema = json.loads((OUTPUT / "MotionComposition.schema.json").read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["asset_bindings"]["additionalProperties"] is False
    with pytest.raises(ValueError, match="refusing"):
        ts_type({"not_a_type": True})


def test_two_shots_share_absolute_frame_boundary_and_recipe_duration_assertions():
    comp, context = fixture()
    graphs = [graph(), graph(cues=[{"id": "start", "at_ms": 0}])]
    durations = [1001, 10999]
    shots = []
    cursor = 0
    for i, duration in enumerate(durations):
        shots.append({"id": f"s{i}", "start_ms": cursor, "duration_ms": duration,
                      "beat": "Fixture", "visual_description": "Original contract fixture"})
        cursor += duration
    context["storyboard"] = CreativeStoryboard(
        direction_id="fixture-direction", duration_ms=12000, fps=30, shots=shots)
    legacy = {"version": 1, "format": "vertical", "tracks": {"video": [
        {"scene_id": s["id"], "duration": s["duration_ms"]/1000,
         "visual_type": "headline", "transition": "cut"} for s in shots]}}
    context["edl"] = from_legacy(legacy, None)
    recipe = MotionRecipe.model_validate({
        "schema_version": "motion_recipe_v1",
        "id": "timing.fixture", "version": "1.0.0", "sha256": "0"*64,
        "canvas": comp.expected.canvas.model_dump(), "scenes": [
            {"shot_slot": f"s{i}", "required_duration_ms": d,
             "graph": graphs[i].model_dump(mode="json")} for i, d in enumerate(durations)]})
    recipe = recipe.model_copy(update={"sha256": recipe_digest(recipe)})
    context["recipe"] = recipe
    data = comp.model_dump(mode="json")
    data.update(asset_bindings={}, recipe={"id": recipe.id, "version": recipe.version,
                                         "sha256": recipe.sha256}, scenes=[
        {"shot_id": f"s{i}", "graph": g.model_dump(mode="json")} for i, g in enumerate(graphs)])
    bound = MotionComposition.model_validate(data)
    report = validate_binding(bound, **context)
    assert [(s["start_frame"], s["end_frame"]) for s in report["shots"]] == [(0, 30), (30, 360)]
    assert report["shots"][1]["cues"][0]["rounding_error_ms_times_3"] == -3
    recipe_data = recipe.model_dump(mode="json")
    recipe_data["scenes"][0]["required_duration_ms"] += 1
    recipe_data["scenes"][1]["required_duration_ms"] -= 1
    changed = MotionRecipe.model_validate(recipe_data)
    changed = changed.model_copy(update={"sha256": recipe_digest(changed)})
    context["recipe"] = changed
    data["recipe"]["sha256"] = changed.sha256
    with pytest.raises(ValueError, match="duration differs from recipe"):
        validate_binding(MotionComposition.model_validate(data), **context)


@pytest.mark.parametrize("kind", ["scene", "composition", "recipe", "registry"])
def test_schema_version_must_be_explicit(kind):
    comp, context = fixture()
    model, data = {
        "scene": (MotionScene, comp.scenes[0].graph.model_dump(mode="json")),
        "composition": (MotionComposition, comp.model_dump(mode="json")),
        "recipe": (MotionRecipe, context["recipe"].model_dump(mode="json")),
        "registry": (RegistryIndex, read_json((REGISTRY_ROOT / "index.json").read_bytes())),
    }[kind]
    data.pop("schema_version")
    with pytest.raises(ValueError, match="schema_version"):
        model.model_validate(data)


@pytest.mark.parametrize("name", ["sports", "music", "geo"])
def test_sound_contract_reuses_existing_edl_mixer(name):
    composition, _ = fixture(name)
    for cue in composition.scenes[0].graph.cues:
        if cue.sound is None:
            continue
        sound = cue.sound
        item = TimelineItem(
            id=cue.id, start_ms=cue.at_ms, duration_ms=sound.duration_ms,
            source_asset_id=composition.asset_bindings[sound.asset_binding].asset_id,
            source_in_ms=sound.source_in_ms,
            source_out_ms=sound.source_in_ms+sound.duration_ms,
            preset="sound_v1", params={"gain": sound.gain,
                "fade_in_ms": sound.fade_in_ms, "fade_out_ms": sound.fade_out_ms})
        assert validate_sound(item).gain == sound.gain


def test_silent_events_and_muted_video_do_not_coerce_flags():
    with pytest.raises(ValueError):
        graph(cues=[{"id": "hit", "at_ms": 0, "sound": {
            "asset_binding": "score", "duration_ms": 1000, "gain": 0}}])
    assert graph(cues=[{"id": "hit", "at_ms": 0}]).cues[0].sound is None
    with pytest.raises(ValueError, match="boolean"):
        VideoParams.model_validate({"asset_binding": "video", "width": 100,
                                    "height": 100, "muted": 1})
