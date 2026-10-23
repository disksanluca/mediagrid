"""Wikimedia pageview drafts must preserve scope and block unreviewed export."""

import copy
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from apps.api import official_trends
from apps.api.config import get_settings
from apps.api.database import SessionLocal
from apps.api.models import Channel, Project
from apps.api.render_plan import render_props
from workers.render.main import source_label

DAY = "2025-05-01"


def wikimedia_response(request: httpx.Request) -> httpx.Response:
    assert request.headers["User-Agent"].startswith("MediaGrid/0.1")
    assert request.url.path.endswith("/pt.wikipedia.org/all-access/2025/05/01")
    return httpx.Response(200, json={"items": [{
        "project": "pt.wikipedia", "access": "all-access",
        "year": "2025", "month": "05", "day": "01",
        "articles": [
            {"article": "Wikipédia:Página_principal", "views": 90000, "rank": 1},
            {"article": "São_Paulo", "views": 17234, "rank": 2},
            {"article": "Especial:Pesquisar", "views": 10000, "rank": 3},
            {"article": "Música_brasileira", "views": 8000, "rank": 4},
        ],
    }]})


def test_wikimedia_search_import_review_and_export(
    client: TestClient, monkeypatch, tmp_path: Path, seed_completed_render,
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    monkeypatch.setattr(official_trends, "analytics_client", lambda: httpx.Client(
        transport=httpx.MockTransport(wikimedia_response),
        headers={"User-Agent": "MediaGrid/0.1 (test)"},
    ))
    channel = client.post("/api/v1/channels", json={
        "name": "Trends com Fontes", "slug": "trends-com-fontes", "niche": "Cultura",
        "default_engine": "trends",
    }).json()
    search = client.get("/api/v1/trends/wiki-top", params={"day": DAY, "query": "sao"})
    assert search.status_code == 200, search.text
    assert [(row["title"], row["rank"]) for row in search.json()] == [
        ("São Paulo", 2),
    ]
    assert "/wiki/" in search.json()[0]["article_url"]
    assert client.get("/api/v1/trends/wiki-top", params={"day": DAY}).status_code == 200
    imported = client.post("/api/v1/trends/projects", json={
        "channel_id": channel["id"], "day": DAY, "article": "São_Paulo",
    })
    assert imported.status_code == 201, imported.text
    project = imported.json()
    project_id = project["id"]
    assert project["content_type"] == "knowledge"
    assert project["plan"]["origin"] == "OFFICIAL_SOURCE"
    assert project["plan"]["engine"] == "trends"
    assert len(project["plan"]["scenes"]) == 3
    assert len(project["plan"]["source_refs"][0]["snapshot_sha256"]) == 64
    assert project["plan"]["source_refs"][0]["data_license"] == "CC0 1.0"
    assert project["plan"]["source_refs"][0]["article"] == "São_Paulo"
    assert project["plan"]["source_refs"][0]["views"] == "17234"
    assert project["plan"]["source_refs"][0]["rank"] == "2"
    assert "17.234" in project["plan"]["scenes"][0]["narration"]
    assert project["plan"]["scenes"][0]["on_screen_text"].startswith("São Paulo\n")
    assert "não audiência no Instagram" in project["plan"]["scenes"][2]["narration"]
    assert source_label(project["plan"]) == "Fonte: Wikimedia Analytics"
    assert project["script"]["segments"] == [
        scene["narration"] for scene in project["plan"]["scenes"]
    ]
    assert len(project["edl"]["tracks"]["video"]) == 3
    with SessionLocal() as db:
        saved = db.get(Project, project_id)
        saved_channel = db.get(Channel, channel["id"])
        assert saved is not None and saved_channel is not None
        props = render_props(saved, saved_channel, saved.edl["tracks"]["video"], [], [], [])
        assert props["editorial_style"] == "wikimedia_trends"
        assert (props["wiki_article"], props["wiki_views"], props["wiki_rank"]) == (
            "São Paulo", 17234, 2,
        )
        edited_edl = dict(saved.edl)
        edited_edl["tracks"] = dict(saved.edl["tracks"])
        edited_edl["tracks"]["captions"] = [
            dict(item) for item in saved.edl["tracks"]["captions"]
        ]
        edited_edl["tracks"]["captions"][0]["text"] = "Legenda editada"
        saved.edl = edited_edl
        edited_props = render_props(
            saved, saved_channel, saved.edl["tracks"]["video"], [], [], [],
        )
        assert "editorial_style" not in edited_props
        assert edited_props["scenes"][0]["on_screen_text"] == "Legenda editada"
        saved.edl = project["edl"]
        altered_plan = copy.deepcopy(saved.plan)
        altered_plan["source_refs"][0]["views"] = "99999"
        saved.plan = altered_plan
        untrusted_props = render_props(
            saved, saved_channel, saved.edl["tracks"]["video"], [], [], [],
        )
        assert "editorial_style" not in untrusted_props
    base = f"/api/v1/projects/{project_id}"
    claims = client.get(f"{base}/claims").json()
    assert len(claims) == 3
    assert all(claim["status"] == "REVIEW_REQUIRED" for claim in claims)
    assert all(claim["published_at"] is None for claim in claims)
    assert sum(bool(claim["source_checked_at"]) for claim in claims) == 2
    assert all(claim["source_checked_at"].endswith("+00:00") for claim in claims
               if claim["source_checked_at"])
    assert {claim["scene_id"] for claim in claims} == {
        scene["id"] for scene in project["plan"]["scenes"]
    }
    seed_completed_render(project_id, b"synthetic-wikimedia-video")
    review = {
        "source_urls": sorted({claim["source_url"] for claim in claims}),
        "facts_confirmed": True, "rights_confirmed": True,
        "notes": "Verificação sintética de gate", "caption": "Pauta em revisão",
    }
    assert client.post(f"{base}/review", json=review).status_code == 409
    assert client.get(f"{base}/export").status_code == 409
    for claim in claims:
        approved = client.post(f"{base}/claims/{claim['id']}/approve", json={
            "expected_revision": 1, "source_opened": True,
            "excerpt_matches": True, "context_checked": True,
        })
        assert approved.status_code == 200, approved.text
    approved = client.post(f"{base}/review", json=review)
    assert approved.status_code == 200, approved.text
    assert client.get(f"{base}/export").status_code == 200
    removed = client.post(f"{base}/claims/{claims[0]['id']}/remove", json={
        "expected_revision": 1,
    })
    assert removed.status_code == 200, removed.text
    assert client.get(f"{base}/export").status_code == 409
    assert client.post(f"{base}/review", json=review).status_code == 409


def test_wikimedia_validation_and_unavailable_source(client: TestClient, monkeypatch) -> None:
    channel = client.post("/api/v1/channels", json={
        "name": "Music", "slug": "music-for-trends", "niche": "Music",
        "default_engine": "music",
    }).json()
    assert client.get("/api/v1/trends/wiki-top", params={
        "day": "2999-01-01",
    }).status_code == 422
    assert client.post("/api/v1/trends/projects", json={
        "channel_id": channel["id"], "day": DAY, "article": "São_Paulo",
    }).status_code == 422
    monkeypatch.setattr(official_trends, "analytics_client", lambda: httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(404)),
    ))
    assert client.get("/api/v1/trends/wiki-top", params={"day": DAY}).status_code == 503
    assert client.get("/api/v1/projects").json() == []
