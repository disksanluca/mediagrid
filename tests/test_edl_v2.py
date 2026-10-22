"""Compatibility must preserve the existing scene renderer's inputs."""

import io
import wave

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.database import SessionLocal
from apps.api.edl_v2 import EDLV2, from_legacy, scene_projection, to_legacy
from apps.api.models import Job


def sample_edl() -> dict:
    return {
        "version": 1,
        "format": "vertical",
        "tracks": {
            "video": [
                {
                    "scene_id": "opening", "duration": 5,
                    "visual_type": "headline", "transition": "impact",
                },
                {
                    "scene_id": "clip", "duration": 7, "visual_type": "image", "transition": "cut",
                    "asset_id": "video-1", "clip_start_seconds": 1, "clip_end_seconds": 3,
                },
            ],
            "audio": [
                {"scene_id": "opening", "text": "Primeira fala"},
                {"scene_id": "clip", "text": "Segunda fala"},
            ],
            "captions": [
                {"scene_id": "opening", "text": "Abertura"},
                {"scene_id": "clip", "text": "Trecho selecionado"},
            ],
        },
    }


def test_v1_roundtrip_keeps_timing_text_and_looped_mp4() -> None:
    original = sample_edl()
    converted = from_legacy(original, None)
    assert converted.version == 2
    assert converted.duration_ms == 12000
    assert [track.kind for track in converted.tracks] == ["video", "voice", "graphic"]
    clip = converted.tracks[0].items[1]
    assert (clip.start_ms, clip.duration_ms, clip.source_in_ms, clip.source_out_ms) == (
        5000, 7000, 1000, 3000,
    )
    assert clip.params["loop"] is True
    restored = to_legacy(converted, "vertical")
    assert restored["tracks"]["audio"] == original["tracks"]["audio"]
    assert restored["tracks"]["captions"] == original["tracks"]["captions"]
    assert restored["tracks"]["video"][1]["clip_end_seconds"] == 3


def test_v1_trim_longer_than_scene_is_preserved_for_truncation() -> None:
    original = sample_edl()
    original["tracks"]["video"][1]["clip_end_seconds"] = 10
    converted = from_legacy(original, None)
    assert converted.tracks[0].items[1].source_out_ms == 10000
    assert to_legacy(converted, "vertical")["tracks"]["video"][1][
        "clip_end_seconds"
    ] == 10


def test_draft_with_empty_voice_is_convertible_but_not_render_ready() -> None:
    old = sample_edl()
    old["tracks"]["audio"][0]["text"] = ""
    assert to_legacy(from_legacy(old, None), "vertical")["tracks"]["audio"][0]["text"] == ""


def test_unimplemented_layers_are_rejected_instead_of_dropped() -> None:
    converted = from_legacy(sample_edl(), None).model_dump()
    converted["tracks"].append({"id": "music", "kind": "music", "items": [{
        "id": "music-1", "start_ms": 0, "duration_ms": 12000,
        "source_asset_id": "song-1", "preset": "sound_v1",
        "params": {"gain": 0.2},
    }]})
    with pytest.raises(ValueError, match="additional tracks"):
        to_legacy(EDLV2.model_validate(converted), "vertical")


def test_source_bounds_and_timeline_bounds_are_checked() -> None:
    converted = from_legacy(sample_edl(), None).model_dump()
    converted["tracks"][0]["items"][1]["source_out_ms"] = 900
    with pytest.raises(ValidationError, match="positive span"):
        EDLV2.model_validate(converted)
    converted = from_legacy(sample_edl(), None).model_dump()
    converted["tracks"][0]["items"][1]["start_ms"] = 10000
    with pytest.raises(ValidationError, match="past project duration"):
        EDLV2.model_validate(converted)


def test_overlay_rejects_unknown_preset_and_invalid_keyframes() -> None:
    converted = from_legacy(sample_edl(), None).model_dump()
    overlay = {
        "id": "overlay-1", "start_ms": 0, "duration_ms": 1000,
        "z_index": 10, "preset": "untrusted_html",
        "params": {"text": "Título", "color": "#dcf769", "keyframes": [
            {"at_ms": 0, "x": 0.5, "y": 0.5, "opacity": 0, "scale": 0.8},
            {"at_ms": 1000, "x": 0.5, "y": 0.5, "opacity": 1, "scale": 1},
        ]},
    }
    converted["tracks"].append({"id": "captions", "kind": "caption", "items": [overlay]})
    with pytest.raises(ValidationError, match="Only local kinetic text"):
        EDLV2.model_validate(converted)
    overlay["preset"] = "kinetic_title_v1"
    overlay["params"]["keyframes"][1]["at_ms"] = 1010
    with pytest.raises(ValidationError, match="within the item"):
        EDLV2.model_validate(converted)


def test_free_video_layer_keeps_scene_projection_and_requires_local_source() -> None:
    converted = from_legacy(sample_edl(), None).model_dump()
    layer = {
        "id": "cutaway-1", "start_ms": 1000, "duration_ms": 1000,
        "z_index": 5, "source_asset_id": "mp4-1",
        "source_in_ms": 2000, "source_out_ms": 3000,
        "preset": "video_overlay_v1",
        "params": {"focus_x": 0.5, "focus_y": 0.4, "opacity": 1},
    }
    converted["tracks"].append({"id": "cutaways", "kind": "video", "items": [layer]})
    edl = EDLV2.model_validate(converted)
    projected, titles, sounds, videos = scene_projection(edl, "vertical")
    assert projected == to_legacy(from_legacy(sample_edl(), None), "vertical")
    assert not titles and not sounds and videos[0].source_in_ms == 2000
    layer["source_out_ms"] = 3500
    with pytest.raises(ValidationError, match="source range and timeline duration"):
        EDLV2.model_validate(converted)


def test_v2_revision_api_preserves_legacy_render_and_rejects_stale_edit(
    client: TestClient,
) -> None:
    channel = client.post("/api/v1/channels", json={
        "name": "Canal EDL", "slug": "canal-edl", "niche": "clips", "default_engine": "clips",
    }).json()
    project = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Teste EDL", "topic": (
            "Primeira frase concreta para a abertura do vídeo local.\n"
            "Segunda frase concreta para a parte central do vídeo.\n"
            "Terceira frase concreta para o encerramento do vídeo."
        ), "format": "vertical",
    }).json()
    project_id = project["id"]
    assert client.post(f"/api/v1/projects/{project_id}/plan").status_code == 200
    url = f"/api/v1/projects/{project_id}/edl-v2"
    first = client.get(url)
    assert first.status_code == 200
    assert first.json()["revision"] == 1
    assert first.headers["etag"] == '"edl-1"'
    payload = {
        "expected_revision": 1,
        "expected_legacy_sha256": first.json()["legacy_sha256"],
        "edl": first.json()["edl"],
    }
    payload["edl"]["tracks"][2]["items"][0]["params"]["text"] = "Título revisado"
    saved = client.put(url, json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 2
    updated = client.get(f"/api/v1/projects/{project_id}").json()
    assert updated["edl"]["version"] == 1
    assert updated["plan"]["scenes"][0]["on_screen_text"] == "Título revisado"
    assert client.put(url, json=payload).status_code == 409
    latest = client.get(url).json()
    assert latest["revision"] == 2
    assert latest["edl"]["revision"] == 3
    latest["edl"]["tracks"].append({
        "id": "unimplemented", "kind": "music", "items": [{
            "id": "song", "start_ms": 0, "duration_ms": 1000,
            "source_asset_id": "song-1", "params": {},
        }],
    })
    assert client.put(url, json={
        "expected_revision": 2,
        "expected_legacy_sha256": latest["legacy_sha256"], "edl": latest["edl"],
    }).status_code == 422


def test_scene_editor_write_advances_revision_and_checks_legacy_hash(
    client: TestClient,
) -> None:
    channel = client.post("/api/v1/channels", json={
        "name": "Canal", "slug": "canal", "niche": "geo", "default_engine": "geo",
    }).json()
    project = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Projeto", "topic": "Tema simples",
        "format": "vertical",
    }).json()
    project_id = project["id"]
    plan = client.post(f"/api/v1/projects/{project_id}/plan").json()
    current = client.get(f"/api/v1/projects/{project_id}/edl-v2").json()
    body = {
        "scenes": plan["scenes"], "hook": plan["hook"], "angle": plan["angle"],
        "expected_revision": current["revision"],
        "expected_legacy_sha256": current["legacy_sha256"],
    }
    saved = client.put(f"/api/v1/projects/{project_id}/plan", json=body)
    assert saved.status_code == 200, saved.text
    assert client.get(f"/api/v1/projects/{project_id}/edl-v2").json()["revision"] == 2
    assert client.put(f"/api/v1/projects/{project_id}/plan", json=body).status_code == 409


def test_kinetic_title_survives_scene_edit_and_reaches_render_job(client: TestClient) -> None:
    channel = client.post("/api/v1/channels", json={
        "name": "Motion local", "slug": "motion-local", "niche": "motion",
        "default_engine": "clips",
    }).json()
    project = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Título animado",
        "topic": (
            "Primeira frase concreta para a abertura do vídeo.\n"
            "Segunda frase concreta para a parte central.\n"
            "Terceira frase concreta para o encerramento."
        ),
    }).json()
    project_id = project["id"]
    plan = client.post(f"/api/v1/projects/{project_id}/plan").json()
    url = f"/api/v1/projects/{project_id}/edl-v2"
    current = client.get(url).json()
    legacy = client.get(f"/api/v1/projects/{project_id}").json()["edl"]
    current["edl"]["tracks"].append({
        "id": "kinetic-titles", "kind": "caption", "items": [{
            "id": "overlay-1", "start_ms": 500, "duration_ms": 2000,
            "z_index": 10, "preset": "kinetic_title_v1",
            "params": {"text": "Texto original", "color": "#dcf769", "keyframes": [
                {"at_ms": 0, "x": 0.5, "y": 0.8, "opacity": 0, "scale": 0.8},
                {"at_ms": 2000, "x": 0.5, "y": 0.7, "opacity": 1, "scale": 1},
            ]},
        }],
    })
    saved = client.put(url, json={
        "expected_revision": current["revision"],
        "expected_legacy_sha256": current["legacy_sha256"],
        "edl": current["edl"],
    })
    assert saved.status_code == 200, saved.text
    after = client.get(url).json()
    assert after["renderer"] == "timeline-v2"
    assert after["edl"]["tracks"][3]["items"][0]["params"]["text"] == "Texto original"
    projected = client.get(f"/api/v1/projects/{project_id}").json()["edl"]
    assert projected["tracks"]["audio"] == legacy["tracks"]["audio"]
    assert projected["tracks"]["captions"] == legacy["tracks"]["captions"]
    assert [item["duration"] for item in projected["tracks"]["video"]] == [
        item["duration"] for item in legacy["tracks"]["video"]
    ]

    plan["scenes"][0]["on_screen_text"] = "Cena revista"
    edited = client.put(f"/api/v1/projects/{project_id}/plan", json={
        "scenes": plan["scenes"], "hook": plan["hook"], "angle": plan["angle"],
        "expected_revision": after["revision"],
        "expected_legacy_sha256": after["legacy_sha256"],
    })
    assert edited.status_code == 200, edited.text
    after = client.get(url).json()
    assert after["renderer"] == "timeline-v2"
    assert after["edl"]["tracks"][3]["items"][0]["params"]["text"] == "Texto original"
    queued = client.post(f"/api/v1/projects/{project_id}/render")
    assert queued.status_code == 202, queued.text
    with SessionLocal() as db:
        job = db.get(Job, queued.json()["job_id"])
        assert job and job.payload["edl_v2"]["tracks"][3]["items"][0]["id"] == "overlay-1"


def test_sound_track_requires_rights_and_reaches_render_job(client: TestClient) -> None:
    channel = client.post("/api/v1/channels", json={
        "name": "Som local", "slug": "som-local", "niche": "motion",
        "default_engine": "clips",
    }).json()
    project = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Mix local",
        "topic": (
            "Primeira frase concreta para a abertura do vídeo.\n"
            "Segunda frase concreta para a parte central.\n"
            "Terceira frase concreta para o encerramento."
        ),
    }).json()
    project_id = project["id"]
    assert client.post(f"/api/v1/projects/{project_id}/plan").status_code == 200
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 16000)
    uploaded = client.post("/api/v1/assets", files={
        "file": ("tone.wav", output.getvalue(), "audio/wav"),
    })
    assert uploaded.status_code == 201, uploaded.text
    asset_id = uploaded.json()["id"]
    url = f"/api/v1/projects/{project_id}/edl-v2"
    current = client.get(url).json()
    current["edl"]["tracks"].append({
        "id": "local-music", "kind": "music", "items": [{
            "id": "sound-1", "start_ms": 0, "duration_ms": 1000,
            "source_asset_id": asset_id, "preset": "sound_v1",
            "params": {"gain": 0.2, "fade_in_ms": 100, "fade_out_ms": 100},
        }],
    })
    payload = {
        "expected_revision": current["revision"],
        "expected_legacy_sha256": current["legacy_sha256"],
        "edl": current["edl"],
    }
    blocked = client.put(url, json=payload)
    assert blocked.status_code == 422
    assert "direitos" in blocked.text
    assert client.patch(f"/api/v1/assets/{asset_id}/rights", json={
        "rights_status": "OWNED", "creator": "Original local",
    }).status_code == 200
    saved = client.put(url, json=payload)
    assert saved.status_code == 200, saved.text
    after = client.get(url).json()
    assert after["renderer"] == "timeline-v2"
    assert after["edl"]["tracks"][3]["items"][0]["source_asset_id"] == asset_id
    queued = client.post(f"/api/v1/projects/{project_id}/render")
    assert queued.status_code == 202, queued.text
    with SessionLocal() as db:
        job = db.get(Job, queued.json()["job_id"])
        assert job and job.payload["edl_v2"]["tracks"][3]["items"][0]["id"] == "sound-1"


def test_video_layer_is_saved_without_becoming_a_scene(client: TestClient) -> None:
    channel = client.post("/api/v1/channels", json={
        "name": "Corte local", "slug": "corte-local", "niche": "clips",
        "default_engine": "clips",
    }).json()
    project = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Camada de vídeo",
        "topic": (
            "Primeira frase concreta para a abertura do vídeo.\n"
            "Segunda frase concreta para a parte central.\n"
            "Terceira frase concreta para o encerramento."
        ),
    }).json()
    project_id = project["id"]
    assert client.post(f"/api/v1/projects/{project_id}/plan").status_code == 200
    asset = client.post("/api/v1/assets", files={
        "file": ("clip.mp4", b"contract-test-placeholder", "video/mp4"),
    }, data={"rights_status": "OWNED"})
    assert asset.status_code == 201, asset.text
    current = client.get(f"/api/v1/projects/{project_id}/edl-v2").json()
    current["edl"]["tracks"].append({
        "id": "cutaways", "kind": "video", "items": [{
            "id": "cutaway-1", "start_ms": 0, "duration_ms": 1000,
            "z_index": 5, "source_asset_id": asset.json()["id"],
            "source_in_ms": 0, "source_out_ms": 1000,
            "preset": "video_overlay_v1",
            "params": {"focus_x": 0.5, "focus_y": 0.5, "opacity": 1},
        }],
    })
    saved = client.put(f"/api/v1/projects/{project_id}/edl-v2", json={
        "expected_revision": current["revision"],
        "expected_legacy_sha256": current["legacy_sha256"],
        "edl": current["edl"],
    })
    assert saved.status_code == 200, saved.text
    legacy = client.get(f"/api/v1/projects/{project_id}").json()["edl"]
    assert len(legacy["tracks"]["video"]) == 3
    revised = client.get(f"/api/v1/projects/{project_id}/edl-v2").json()
    assert revised["renderer"] == "timeline-v2"
    assert revised["edl"]["tracks"][-1]["items"][0]["id"] == "cutaway-1"
