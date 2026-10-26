"""Deterministic compiler for approved Creative Director inputs; no project mutations."""

import json
import subprocess
import wave
from fractions import Fraction
from pathlib import Path

from fastapi import HTTPException
from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from ..config import get_settings
from ..edl_v2 import EDLV2, TimelineItem, TimelineTrack, from_legacy
from ..ingestion import sha256_file
from ..models import (
    CreativeBriefRevision,
    CreativeDirectionSet,
    CreativeDNARevision,
    CreativeStoryboardRevision,
    KnowledgeClaim,
)
from ..motion_contracts.canonical import contract_sha256
from ..motion_contracts.fonts import font_source, layout_text
from ..motion_contracts.models import (
    AssetBinding,
    MotionComposition,
    MotionRecipe,
)
from ..motion_contracts.registry import REGISTRY_ROOT, load_recipe, recipe_digest
from ..motion_contracts.render import MotionSceneSpec
from ..motion_contracts.requests import EngineParameters, EngineRequest
from ..motion_contracts.validation import slots_used, validate_binding
from ..scene_media import scene_asset, sound_asset
from .contracts import CreativeDNA, CreativeStoryboard
from .hashing import content_sha256
from .motion import enqueue_motion_payload, runtime_manifest
from .service import latest, project_for, review_read, serialized


def recipes_read() -> dict:
    index = json.loads((REGISTRY_ROOT / "index.json").read_text(encoding="utf-8"))
    recipes = [load_recipe(r["id"], r["version"]) for r in index["recipes"]]
    return {
        "schema_version": "motion_capabilities_v1",
        "fonts": ["Barlow Condensed"],
        "fps": 30,
        "parameters": EngineParameters.model_json_schema(),
        "recipes": [
            {
                **r.model_dump(include={"id", "version", "sha256", "canvas", "asset_slots"}),
                "shots": [
                    {"slot": s.shot_slot, "reference_duration_ms": s.required_duration_ms}
                    for s in r.scenes
                ],
                "status": "SUPPORTED" if r.version == "1.1.0" else "CONTRACT_REFERENCE",
            }
            for r in recipes
        ],
        "scout": "NOT_IMPLEMENTED",
        "publishing": False,
    }


def instantiate(recipe: MotionRecipe, shots, parameters: EngineParameters) -> MotionRecipe:
    if len(recipe.scenes) != len(shots):
        raise ValueError("RECIPE_SHOTS: storyboard must have the recipe's shot count")
    data = recipe.model_dump(mode="json")
    reference_start = 0
    for template, shot in zip(data["scenes"], shots, strict=True):
        original_duration = template["required_duration_ms"]
        factor = shot.duration_ms / template["required_duration_ms"]
        template["required_duration_ms"] = shot.duration_ms

        def scale(value, factor=factor):
            if isinstance(value, list):
                for entry in value:
                    scale(entry)
            elif isinstance(value, dict):
                for key, entry in value.items():
                    if key in {"at_ms", "offset_ms", "duration_ms", "fade_in_ms", "fade_out_ms"}:
                        value[key] = round(entry * factor)
                    elif key == "active_ms" and entry is not None:
                        value[key] = [round(t * factor) for t in entry]
                    else:
                        scale(entry)

        scale(template["graph"])
        for node in template["graph"]["nodes"]:
            if node["type"] == "text":
                node["params"]["size"] = round(node["params"]["size"] * parameters.text_scale, 6)
            if node["type"] == "video" and node["params"]["source_in_ms"] == reference_start:
                node["params"]["source_in_ms"] = shot.start_ms
        for cue in template["graph"]["cues"]:
            if cue["sound"]:
                cue["sound"]["gain"] = round(cue["sound"]["gain"] * parameters.audio_gain, 6)
                if cue["sound"]["source_in_ms"] == reference_start:
                    cue["sound"]["source_in_ms"] = shot.start_ms
        reference_start += original_duration
    instance = MotionRecipe.model_validate(data)
    return instance.model_copy(update={"sha256": recipe_digest(instance)})


def asset_metadata(db: Session, asset_id: str, kind: str):
    asset = sound_asset(db, asset_id) if kind == "audio" else scene_asset(db, asset_id)
    base = (get_settings().mediagrid_data_dir / "assets").resolve()
    source = base / asset.id
    if not source.resolve().is_relative_to(base) or source.is_symlink():
        raise ValueError("Asset path escapes library")
    size = source.stat().st_size
    if not 0 < size <= 128 * 1024 * 1024 or not asset.commercial_use:
        raise ValueError("Asset size/rights blocked")
    if sha256_file(source) != asset.sha256:
        raise ValueError("Asset physical SHA-256 changed")
    if asset.media_type in {"audio/wav", "audio/x-wav"} and kind == "audio":
        with wave.open(str(source), "rb") as wav:
            info = {
                "sample_rate": wav.getframerate(),
                "channels": wav.getnchannels(),
                "duration_ms": round(wav.getnframes() * 1000 / wav.getframerate()),
            }
    else:
        result = subprocess.run(
            [
                str(get_settings().mediagrid_ffprobe_path or "ffprobe"),
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(source),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
        probe = json.loads(result.stdout)
        streams = probe["streams"]
        stream = next(
            (s for s in streams if s["codec_type"] == ("audio" if kind == "audio" else "video")),
            None,
        )
        if stream is None:
            raise ValueError("Asset kind differs from decoded stream")
        mime_codecs = {
            "image/png": "png",
            "image/jpeg": "mjpeg",
            "image/webp": "webp",
            "audio/mpeg": "mp3",
        }
        if (
            asset.media_type in mime_codecs
            and stream["codec_name"] != mime_codecs[asset.media_type]
        ):
            raise ValueError("Asset MIME differs from decoded content")
        if kind == "image" and asset.media_type not in mime_codecs:
            raise ValueError("An image slot requires a supported still image")
        if kind == "video" and asset.media_type != "video/mp4":
            raise ValueError("A video slot requires MP4")
        info = (
            {"sample_rate": int(stream["sample_rate"]), "channels": stream["channels"]}
            if kind == "audio"
            else {"width": stream["width"], "height": stream["height"]}
        )
        if kind != "image":
            info["duration_ms"] = round(
                float(stream.get("duration") or probe["format"]["duration"]) * 1000
            )
        if kind == "video":
            fps = Fraction(stream["avg_frame_rate"])
            info.update(fps_num=fps.numerator, fps_den=fps.denominator)
    metadata = TypeAdapter(AssetBinding).validate_python(
        {
            "kind": kind,
            "asset_id": asset.id,
            "sha256": asset.sha256,
            "byte_size": size,
            **info,
        }
    )
    provenance = {
        name: getattr(asset, name)
        for name in (
            "id",
            "sha256",
            "rights_status",
            "license_name",
            "creator",
            "source_url",
            "commercial_use",
        )
    }
    return metadata, provenance


def derive_engine(db: Session, project_id: str, request: EngineRequest) -> dict:
    project = project_for(db, project_id)
    state = review_read(db, project)
    board = latest(db, CreativeStoryboardRevision, project_id)
    if (
        state["status"] != "APPROVED_STORYBOARD"
        or state["blockers"]
        or state["current_snapshot_sha256"] != request.expected_snapshot_sha256
        or board.revision != request.expected_storyboard_revision
    ):
        raise HTTPException(409, "Current storyboard approval/revision/snapshot required")
    brief = latest(db, CreativeBriefRevision, project_id)
    dna = latest(db, CreativeDNARevision, project.channel_id)
    directions = latest(db, CreativeDirectionSet, project_id)
    storyboard = CreativeStoryboard.model_validate(board.payload)
    identity = CreativeDNA.model_validate(dna.payload)
    try:
        template = load_recipe(request.recipe.id, request.recipe.version)
        if template.version != "1.1.0" or template.sha256 != request.recipe.sha256:
            raise ValueError("RECIPE_NOT_SUPPORTED or recipe hash changed")
        if (identity.font_display, identity.font_body) != ("Barlow Condensed",) * 2:
            raise ValueError("FONT_UNSUPPORTED: use the bundled Barlow Condensed in DNA")
        recipe = instantiate(template, storyboard.shots, request.parameters)
        if set(request.asset_bindings) != set(recipe.asset_slots):
            raise ValueError("Asset bindings must match the recipe slots exactly")
        assets, provenance = {}, []
        for slot, kind in recipe.asset_slots.items():
            asset_id = request.asset_bindings[slot]
            if asset_id not in brief.payload["asset_ids"]:
                raise ValueError("Asset is not in the approved brief")
            assets[slot], record = asset_metadata(db, asset_id, kind)
            provenance.append({**record, "slot": slot, "metadata": assets[slot].model_dump()})
        legacy = {
            "version": 1,
            "format": project.format,
            "tracks": {
                "video": [
                    {
                        "scene_id": s.id,
                        "duration": s.duration_ms / 1000,
                        "visual_type": "headline",
                        "transition": "cut",
                    }
                    for s in storyboard.shots
                ],
                "audio": [{"scene_id": s.id, "text": ""} for s in storyboard.shots],
                "captions": [{"scene_id": s.id, "text": ""} for s in storyboard.shots],
            },
        }
        edl = from_legacy(legacy, None, revision=board.revision)
        claims = {
            row.id: {"text": row.text, "source_label": row.source_title}
            for row in db.query(KnowledgeClaim)
            .filter_by(project_id=project_id, status="APPROVED")
            .all()
        }
        composition = MotionComposition.model_validate(
            {
                "schema_version": "motion_composition_v1",
                "project_id": project_id,
                "expected": {
                    "storyboard_revision": board.revision,
                    "snapshot_sha256": state["current_snapshot_sha256"],
                    "canvas": edl.canvas.model_dump(),
                    "duration_ms": edl.duration_ms,
                },
                "recipe": recipe.model_dump(include={"id", "version", "sha256"}),
                "asset_bindings": {k: a.model_dump() for k, a in assets.items()},
                "scenes": [
                    {"shot_id": s.id, "graph": t.graph.model_dump()}
                    for s, t in zip(storyboard.shots, recipe.scenes, strict=True)
                ],
            }
        )
        validation = validate_binding(
            composition,
            edl=edl,
            storyboard=storyboard,
            dna=identity,
            project_id=project_id,
            storyboard_revision=board.revision,
            snapshot_sha256=state["current_snapshot_sha256"],
            available_assets={a.asset_id: a for a in assets.values()},
            approved_claims=claims,
            recipe=recipe,
        )
        overlays, sounds, measurements = [], [], {}
        for scene, shot in zip(composition.scenes, storyboard.shots, strict=True):
            texts = {}
            for node in scene.graph.nodes:
                if node.type == "group" and node.anchor != [0, 0]:
                    raise ValueError("Group anchors must be [0,0] in engine v1")
                if node.type != "text":
                    continue
                binding = node.params.text
                text = (
                    shot.on_screen_text
                    if binding.kind == "shot_field"
                    else claims[binding.claim_id][binding.field]
                )
                texts[node.id], measurements[f"{shot.id}/{node.id}"] = layout_text(
                    text, node.params.size, node.params.max_width, node.params.max_lines
                )
            used = {slot for slot, _ in slots_used(scene.graph)}
            spec = MotionSceneSpec(
                schema_version="motion_scene_render_v1",
                graph=scene.graph,
                palette=identity.palette,
                fonts=[identity.font_display, identity.font_body],
                texts=texts,
                assets={slot: assets[slot].asset_id for slot in sorted(used)},
                diagnostics=request.parameters.diagnostics,
            )
            overlays.append(
                TimelineItem(
                    id=f"motion-{shot.id}",
                    start_ms=shot.start_ms,
                    duration_ms=shot.duration_ms,
                    z_index=10,
                    preset="motion_scene_v1",
                    params={"motion": spec.model_dump(mode="json")},
                )
            )
            for cue in scene.graph.cues:
                if cue.sound:
                    sound = cue.sound
                    sounds.append(
                        TimelineItem(
                            id=f"sound-{shot.id}-{cue.id}",
                            start_ms=shot.start_ms + cue.at_ms,
                            duration_ms=sound.duration_ms,
                            source_asset_id=assets[sound.asset_binding].asset_id,
                            source_in_ms=sound.source_in_ms,
                            source_out_ms=sound.source_in_ms + sound.duration_ms,
                            preset="sound_v1",
                            params={
                                "gain": sound.gain,
                                "fade_in_ms": sound.fade_in_ms,
                                "fade_out_ms": sound.fade_out_ms,
                                "loop": False,
                            },
                        )
                    )
        edl.tracks.extend(
            [
                TimelineTrack(id="motion-design", kind="caption", items=overlays),
                TimelineTrack(id="motion-sound", kind="music", items=sounds),
            ]
        )
        edl = EDLV2.model_validate(edl.model_dump())
    except (ValueError, OSError, wave.Error, KeyError, subprocess.SubprocessError) as exc:
        raise HTTPException(422, str(exc)) from exc
    selected = next(
        d for d in directions.payload["directions"] if d["id"] == storyboard.direction_id
    )
    module_root = Path(__file__).resolve().parents[1]
    runtime = runtime_manifest()
    runtime["engine_files"] = {
        str(p.relative_to(module_root)).replace("\\", "/"): sha256_file(p)
        for p in sorted([*(module_root / "motion_contracts").glob("*.py"), Path(__file__)])
    }
    runtime["font_license_sha256"] = sha256_file(font_source().with_name("sports-font-OFL.txt"))
    runtime["worker_files"] = {
        name: sha256_file(module_root.parents[1] / "workers" / "render" / name)
        for name in ("creative_motion.py", "remotion_runtime.py")
    }
    renderer = get_settings().mediagrid_renderer_root or module_root.parents[1] / "apps/renderer"
    packages = {}
    for name in ("remotion", "@remotion/cli", "react", "react-dom"):
        candidates = [
            renderer / "node_modules" / name / "package.json",
            renderer.parents[1] / "node_modules" / name / "package.json",
        ]
        package = next((path for path in candidates if path.is_file()), None)
        if package is None:
            raise HTTPException(409, f"Renderer dependency unavailable: {name}")
        packages[name] = {
            "version": json.loads(package.read_text())["version"],
            "package_sha256": sha256_file(package),
        }
    runtime["packages"] = packages
    plan = {
        "schema_version": "creative_motion_engine_v1",
        "project_id": project_id,
        "title": project.title,
        "format": project.format,
        "approved_snapshot_sha256": state["current_snapshot_sha256"],
        "approval": state["review"],
        "storyboard": serialized(board),
        "brief": serialized(brief),
        "dna": serialized(dna),
        "direction": {
            "set_id": directions.id,
            "revision": directions.revision,
            "sha256": directions.sha256,
            "selected": selected,
        },
        "recipe_template": template.model_dump(mode="json"),
        "expanded_recipe": recipe.model_dump(mode="json"),
        "composition": composition.model_dump(mode="json"),
        "composition_sha256": contract_sha256(composition),
        "assets": provenance,
        "text_measurements": measurements,
        "validation": validation,
        "edl_v2": edl.model_dump(mode="json"),
        "runtime": runtime,
        "approval_scope": "STORYBOARD_INPUT_ONLY; AUDIOVISUAL_REVIEW_PENDING",
        "render": {
            "composition": "MediaGridTimelineV2",
            "codec": "h264",
            "audio_codec": "aac",
            "fps": 30,
            "frames": round(edl.duration_ms * 30 / 1000),
            "width": edl.canvas.width,
            "height": edl.canvas.height,
            "duration_ms": edl.duration_ms,
            "audio_required": bool(sounds),
            "scale": 0.5 if request.quality == "preview" else 1,
            "crf": 18,
            "audio_bitrate": "192k",
            "quality": request.quality,
        },
        "request": request.model_dump(mode="json"),
    }
    plan["dependencies_sha256"] = contract_sha256(
        {
            "snapshot": plan["approved_snapshot_sha256"],
            "assets": plan["assets"],
            "runtime": runtime,
            "recipe": request.recipe.model_dump(),
        }
    )
    return {"plan": plan, "plan_sha256": content_sha256(plan)}


def verify_engine(db, project_id, payload):
    if content_sha256(payload.get("plan")) != payload.get("plan_sha256"):
        raise ValueError("Derived motion payload hash mismatch")
    try:
        current = derive_engine(
            db, project_id, EngineRequest.model_validate(payload["plan"]["request"])
        )
    except HTTPException as exc:
        raise ValueError(f"Motion engine blocked: {exc.detail}") from exc
    if current != payload:
        raise ValueError("Motion dependencies/runtime changed after preparation")
    return payload["plan"]


def queue_engine(db, project_id, request):
    return enqueue_motion_payload(db, project_id, derive_engine(db, project_id, request))
