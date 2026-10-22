"""Compatibility must preserve the existing scene renderer's inputs."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.edl_v2 import EDLV2, from_legacy, to_legacy


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


def test_draft_with_empty_voice_is_convertible_but_not_render_ready() -> None:
    old = sample_edl()
    old["tracks"]["audio"][0]["text"] = ""
    assert to_legacy(from_legacy(old, None), "vertical")["tracks"]["audio"][0]["text"] == ""


def test_unimplemented_layers_are_rejected_instead_of_dropped() -> None:
    converted = from_legacy(sample_edl(), None).model_dump()
    converted["tracks"].append({"id": "music", "kind": "music", "items": [{
        "id": "music-1", "start_ms": 0, "duration_ms": 12000,
        "source_asset_id": "song-1", "params": {},
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
