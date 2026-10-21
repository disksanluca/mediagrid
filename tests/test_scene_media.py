import base64
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.config import get_settings
from apps.api.database import SessionLocal
from apps.api.scene_media import stage_scene_assets

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+nmF8AAAAASUVORK5CYII="
)


def test_uploaded_image_is_persisted_in_scene_and_staged_for_render(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    channel = client.post(
        "/api/v1/channels",
        json={
            "name": "Canal local",
            "slug": "canal-local",
            "niche": "Política",
            "default_engine": "politics",
        },
    ).json()
    project = client.post(
        "/api/v1/projects",
        json={
            "channel_id": channel["id"],
            "title": "Pauta verificada",
            "topic": "Primeiro fato do documento oficial com contexto suficiente.\n"
            "Segundo fato do documento oficial com contexto suficiente.\n"
            "Terceiro fato do documento oficial com contexto suficiente.",
        },
    ).json()
    project_id = project["id"]
    plan = client.post(f"/api/v1/projects/{project_id}/plan").json()
    assert plan["origin"] == "BRIEF_BASED"
    asset = client.post(
        "/api/v1/assets",
        files={"file": ("foto.png", PNG, "image/png")},
    ).json()
    plan["scenes"][0]["asset_id"] = asset["id"]
    payload = {"scenes": plan["scenes"], "hook": plan["hook"], "angle": plan["angle"]}
    assert client.put(f"/api/v1/projects/{project_id}/plan", json=payload).status_code == 422
    assert client.patch(
        f"/api/v1/assets/{asset['id']}/rights",
        json={"rights_status": "LICENSED"},
    ).status_code == 422
    assert client.patch(
        f"/api/v1/assets/{asset['id']}/rights",
        json={"rights_status": "OWNED", "creator": "Usuário", "commercial_use": True},
    ).status_code == 200
    saved = client.put(f"/api/v1/projects/{project_id}/plan", json=payload)
    assert saved.status_code == 200
    assert saved.json()["edl"]["tracks"]["video"][0]["asset_id"] == asset["id"]
    assert client.post(f"/api/v1/projects/{project_id}/render").status_code == 202

    with SessionLocal() as db:
        staged = stage_scene_assets(
            db, saved.json()["edl"]["tracks"]["video"], tmp_path / "render-public"
        )
    assert staged[asset["id"]] == {"media_kind": "image", "media_file": f"{asset['id']}.png"}
    assert (tmp_path / "render-public" / f"{asset['id']}.png").read_bytes() == PNG


def test_scene_media_rejects_unknown_asset_and_rights_change(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    channel = client.post(
        "/api/v1/channels",
        json={
            "name": "Canal local",
            "slug": "canal-local",
            "niche": "Política",
            "default_engine": "politics",
        },
    ).json()
    project = client.post(
        "/api/v1/projects",
        json={"channel_id": channel["id"], "title": "Tema", "topic": "Assunto em verificação"},
    ).json()
    plan = client.post(f"/api/v1/projects/{project['id']}/plan").json()
    for index, scene in enumerate(plan["scenes"]):
        scene["narration"] = f"Cena {index + 1} redigida a partir de fonte verificada."
    plan["scenes"][0]["asset_id"] = "nao-existe"
    payload = {"scenes": plan["scenes"], "hook": plan["hook"], "angle": plan["angle"]}
    assert client.put(f"/api/v1/projects/{project['id']}/plan", json=payload).status_code == 422
    asset = client.post(
        "/api/v1/assets",
        files={"file": ("foto.png", PNG, "image/png")},
        data={"rights_status": "OWNED"},
    ).json()
    payload["scenes"][0]["asset_id"] = asset["id"]
    assert client.put(f"/api/v1/projects/{project['id']}/plan", json=payload).status_code == 200
    client.patch(
        f"/api/v1/assets/{asset['id']}/rights",
        json={"rights_status": "RESTRICTED"},
    )
    assert client.post(f"/api/v1/projects/{project['id']}/render").status_code == 422
