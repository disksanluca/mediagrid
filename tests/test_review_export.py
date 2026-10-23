import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.config import get_settings
from apps.api.database import SessionLocal
from apps.api.models import Project, ProjectStatus


def test_manual_export_requires_review_and_is_revoked_after_edit(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    channel = client.post(
        "/api/v1/channels",
        json={
            "name": "Canal geral",
            "slug": "canal-geral",
            "niche": "Vídeo",
            "default_engine": "music",
        },
    ).json()
    project = client.post(
        "/api/v1/projects",
        json={
            "channel_id": channel["id"],
            "title": "Projeto de lei",
            "topic": "Analisar documento oficial",
        },
    ).json()
    project_id = project["id"]
    plan = client.post(f"/api/v1/projects/{project_id}/plan").json()
    assert client.get(f"/api/v1/projects/{project_id}/export").status_code == 409

    with SessionLocal() as db:
        stored = db.get(Project, project_id)
        assert stored is not None
        stored.status = ProjectStatus.QC.value
        db.commit()
    render_dir = tmp_path / "renders"
    render_dir.mkdir()
    (render_dir / f"{project_id}.mp4").write_bytes(b"local-test-video")

    review = {
        "source_urls": ["https://example.org/documento"],
        "facts_confirmed": True,
        "rights_confirmed": False,
        "notes": "Conferido com documento oficial",
        "caption": "Resumo para publicação após conferência dos fatos.",
    }
    assert client.post(f"/api/v1/projects/{project_id}/review", json=review).status_code == 409
    review["rights_confirmed"] = True
    approved = client.post(f"/api/v1/projects/{project_id}/review", json=review)
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"
    assert client.get(f"/api/v1/projects/{project_id}/output").status_code == 200

    package = client.get(f"/api/v1/projects/{project_id}/export")
    assert package.status_code == 200
    with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
        assert archive.read("video.mp4") == b"local-test-video"
        assert archive.read("caption.txt").decode() == review["caption"]
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["publication"] == "manual"
    assert manifest["platform_status"] == "not_published"
    assert manifest["approved_review"]["source_urls"] == ["https://example.org/documento"]
    assert len(manifest["approved_review"]["video_sha256"]) == 64
    assert len(manifest["approved_review"]["edl_sha256"]) == 64

    video = render_dir / f"{project_id}.mp4"
    video.write_bytes(b"tampered-after-approval")
    assert client.get(f"/api/v1/projects/{project_id}/export").status_code == 409
    video.write_bytes(b"local-test-video")

    for index, scene in enumerate(plan["scenes"]):
        scene["narration"] = f"Cena {index + 1} revisada com o documento oficial."
    changed = client.put(
        f"/api/v1/projects/{project_id}/plan",
        json={"scenes": plan["scenes"], "hook": plan["hook"], "angle": plan["angle"]},
    )
    assert changed.status_code == 200
    assert changed.json()["status"] == "SCRIPTED"
    assert client.get(f"/api/v1/projects/{project_id}/export").status_code == 409

    with SessionLocal() as db:
        stored = db.get(Project, project_id)
        assert stored is not None
        stored.status = ProjectStatus.QC.value
        db.commit()
    assert client.post(f"/api/v1/projects/{project_id}/review", json=review).status_code == 200
    assert client.post(f"/api/v1/projects/{project_id}/render").status_code == 202
    refreshed = client.get(f"/api/v1/projects/{project_id}").json()
    assert refreshed["status"] == "SCRIPTED"
    assert "review" not in refreshed["plan"]
    assert client.get(f"/api/v1/projects/{project_id}/export").status_code == 409
