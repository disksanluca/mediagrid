import hashlib
import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.config import get_settings
from apps.api.database import SessionLocal
from apps.api.models import Project, ProjectStatus
from apps.api.routes.projects import latest_revision, legacy_hash


def test_qc_requires_the_matching_completed_render(
    client: TestClient, monkeypatch, tmp_path: Path, seed_completed_render,
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    channel = client.post("/api/v1/channels", json={
        "name": "Integridade", "slug": "integridade", "niche": "Vídeo",
        "default_engine": "music",
    }).json()
    project_id = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Hash do render",
        "topic": "Saída precisa corresponder ao job",
    }).json()["id"]
    client.post(f"/api/v1/projects/{project_id}/plan")
    base = f"/api/v1/projects/{project_id}"
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        assert project is not None
        project.status = ProjectStatus.QC.value
        db.commit()
    output = tmp_path / "renders" / f"{project_id}.mp4"
    output.parent.mkdir()
    output.write_bytes(b"orphaned-file")
    assert client.get(f"{base}/output").status_code == 409
    assert client.post(f"{base}/review", json={
        "source_urls": ["https://example.org/source"],
        "facts_confirmed": True, "rights_confirmed": True,
        "notes": "Revisão sintética de integridade",
    }).status_code == 409
    seed_completed_render(project_id, b"verified-file")
    assert client.get(f"{base}/output").status_code == 200
    output.write_bytes(b"changed-after-render")
    assert client.get(f"{base}/output").status_code == 409


def test_preexisting_approved_render_remains_accessible(
    client: TestClient, monkeypatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    channel = client.post("/api/v1/channels", json={
        "name": "Arquivo anterior", "slug": "arquivo-anterior", "niche": "Vídeo",
        "default_engine": "music",
    }).json()
    project_id = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Aprovado antes do hash do job",
        "topic": "Preservar a revisão humana existente",
    }).json()["id"]
    client.post(f"/api/v1/projects/{project_id}/plan")
    output = tmp_path / "renders" / f"{project_id}.mp4"
    output.parent.mkdir()
    output.write_bytes(b"legacy-approved-video")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        assert project is not None and project.edl
        revision = latest_revision(db, project_id)
        review = {
            "video_sha256": digest,
            "edl_sha256": legacy_hash(project.edl),
            "revision_sha256": revision.sha256 if revision else None,
        }
        project.plan = {**(project.plan or {}), "review": review}
        project.status = ProjectStatus.APPROVED.value
        db.commit()
    base = f"/api/v1/projects/{project_id}"
    assert client.get(f"{base}/output").status_code == 200
    output.write_bytes(b"changed-legacy-video")
    assert client.get(f"{base}/output").status_code == 409


def test_manual_export_requires_review_and_is_revoked_after_edit(
    client: TestClient, monkeypatch, tmp_path: Path, seed_completed_render,
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

    video = seed_completed_render(project_id, b"local-test-video")

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

    video.write_bytes(b"tampered-after-approval")
    assert client.get(f"/api/v1/projects/{project_id}/output").status_code == 409
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

    assert client.post(f"/api/v1/projects/{project_id}/review", json=review).status_code == 409
    assert client.post(f"/api/v1/projects/{project_id}/render").status_code == 202
    refreshed = client.get(f"/api/v1/projects/{project_id}").json()
    assert refreshed["status"] == "SCRIPTED"
    assert "review" not in refreshed["plan"]
    assert client.get(f"/api/v1/projects/{project_id}/export").status_code == 409
