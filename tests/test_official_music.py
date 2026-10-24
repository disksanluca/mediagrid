from copy import deepcopy

import httpx
import pytest
from fastapi.testclient import TestClient

from apps.api import official_music
from apps.api.config import get_settings

RELEASE_ID = "b29e94e7-0b0b-3a66-ab06-e02f8fa5054f"
RELEASE = {
    "id": RELEASE_ID,
    "title": "Clube da Esquina",
    "artist-credit": [
        {"name": "Milton Nascimento", "joinphrase": " & "},
        {"name": "Lô Borges", "joinphrase": ""},
    ],
    "first-release-date": "1972",
    "primary-type": "Album",
}


def musicbrainz_response(request: httpx.Request) -> httpx.Response:
    assert request.url.host == "musicbrainz.org"
    assert request.headers["user-agent"].startswith("MediaGrid/0.1")
    if request.url.path == "/ws/2/release-group/":
        assert request.url.params["query"] == "Clube da Esquina"
        assert request.url.params["fmt"] == "json"
        return httpx.Response(200, json={"release-groups": [RELEASE]})
    assert request.url.path == f"/ws/2/release-group/{RELEASE_ID}"
    assert request.url.params["inc"] == "artist-credits"
    return httpx.Response(200, json=RELEASE)


def test_musicbrainz_import_persists_source_and_review_gate(
    client: TestClient, monkeypatch, tmp_path, seed_completed_render,
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    monkeypatch.setattr(official_music.time, "sleep", lambda _: None)
    monkeypatch.setattr(official_music, "musicbrainz_client", lambda: httpx.Client(
        transport=httpx.MockTransport(musicbrainz_response),
        headers={"User-Agent": "MediaGrid/0.1 (https://github.com/disksanluca/mediagrid)"},
    ))
    channel = client.post("/api/v1/channels", json={
        "name": "Música", "slug": "musica-fonte", "niche": "Música",
        "default_engine": "music",
    }).json()
    results = client.get("/api/v1/music/release-groups", params={
        "query": "Clube da Esquina",
    })
    assert results.status_code == 200, results.text
    assert results.json()[0]["artist"] == "Milton Nascimento & Lô Borges"
    project_response = client.post("/api/v1/music/projects", json={
        "channel_id": channel["id"], "release_group_id": RELEASE_ID,
    })
    assert project_response.status_code == 201, project_response.text
    project = project_response.json()
    assert project["content_type"] == "knowledge"
    plan = project["plan"]
    assert plan["origin"] == "OFFICIAL_SOURCE"
    assert plan["engine"] == "music"
    assert len(plan["scenes"]) == 3
    assert "1972" in plan["scenes"][1]["narration"]
    assert len(plan["source_refs"][0]["snapshot_sha256"]) == 64
    assert plan["source_refs"][0]["data_license"] == "CC0 core data"
    assert "audio" not in plan["source_refs"][0]
    project_id = project["id"]
    base = f"/api/v1/projects/{project_id}"
    preview = client.get(f"{base}/preview")
    assert preview.status_code == 200, preview.text
    props = preview.json()["props"]
    assert props["editorial_style"] == "musicbrainz_metadata"
    assert props["source_label"] == "Fonte: MusicBrainz"
    assert props["music_title"] == "Clube da Esquina"
    assert props["music_artist"] == "Milton Nascimento & Lô Borges"
    assert props["music_first_release_date"] == "1972"
    assert props["music_record_id"] == RELEASE_ID
    assert props["source_checked_at"]
    claims = client.get(f"{base}/claims").json()
    assert len(claims) == 3
    assert all(claim["status"] == "REVIEW_REQUIRED" for claim in claims)
    assert {claim["scene_id"] for claim in claims} == {
        scene["id"] for scene in plan["scenes"]
    }
    seed_completed_render(project_id, b"synthetic-music-video")
    review = {
        "source_urls": sorted({claim["source_url"] for claim in claims}),
        "facts_confirmed": True, "rights_confirmed": True,
        "notes": "Metadados conferidos no registro", "caption": "Revisão de teste",
    }
    assert client.post(f"{base}/review", json=review).status_code == 409
    assert client.get(f"{base}/export").status_code == 409
    for claim in claims:
        approved = client.post(f"{base}/claims/{claim['id']}/approve", json={
            "expected_revision": claim["revision"], "source_opened": True,
            "excerpt_matches": True, "context_checked": True,
        })
        assert approved.status_code == 200, approved.text
    assert client.post(f"{base}/review", json=review).status_code == 200
    assert client.get(f"{base}/export").status_code == 200
    edited_plan = deepcopy(plan)
    edited_plan["scenes"][0]["narration"] = "Texto revisado pela equipe."
    changed = client.put(f"{base}/plan", json={
        "hook": edited_plan["hook"], "angle": edited_plan["angle"],
        "scenes": edited_plan["scenes"],
    })
    assert changed.status_code == 200, changed.text
    assert client.get(f"{base}/preview").json()["props"]["editorial_style"] == (
        "musicbrainz_metadata"
    )
    assert client.get(f"{base}/export").status_code == 409


def test_musicbrainz_rejects_untrusted_metadata_and_unavailable_provider(
    client: TestClient, monkeypatch,
) -> None:
    with pytest.raises(ValueError):
        official_music._release_group({**RELEASE, "id": "not-a-uuid"})
    with pytest.raises(ValueError):
        official_music._release_group({**RELEASE, "title": "Unsafe\nheadline"})
    with pytest.raises(ValueError):
        official_music._release_group({**RELEASE, "first-release-date": "1972-99"})
    channel = client.post("/api/v1/channels", json={
        "name": "Geo", "slug": "geo-not-music", "niche": "Geo",
        "default_engine": "geo",
    }).json()
    assert client.post("/api/v1/music/projects", json={
        "channel_id": channel["id"], "release_group_id": RELEASE_ID,
    }).status_code == 422
    assert client.get("/api/v1/music/release-groups", params={"query": "ab"}).status_code == 422
    monkeypatch.setattr(official_music, "musicbrainz_client", lambda: httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(503)),
    ))
    assert client.get("/api/v1/music/release-groups", params={
        "query": "Clube da Esquina",
    }).status_code == 503
    monkeypatch.setattr(official_music, "musicbrainz_client", lambda: httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(
            200, content=b"x" * (official_music.MAX_RESPONSE_BYTES + 1),
        )),
    ))
    assert client.get("/api/v1/music/release-groups", params={
        "query": "Clube da Esquina",
    }).status_code == 503
    assert client.get("/api/v1/projects").json() == []
