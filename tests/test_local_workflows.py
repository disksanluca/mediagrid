import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.config import get_settings
from apps.api.database import SessionLocal
from apps.api.local_media import narration_text, voice_matches
from apps.api.models import Channel, Project
from apps.api.services import build_local_plan, enrich_plan_with_local_ai, local_ollama_url
from workers.render.main import backup_local_database, media_one


def test_local_library_and_transcription_queue(client: TestClient) -> None:
    response = client.post(
        "/api/v1/assets",
        files={"file": ("voice.wav", b"RIFFexample", "audio/wav")},
        data={"rights_status": "OWNED"},
    )
    assert response.status_code == 201
    asset = response.json()
    assert asset["rights_status"] == "OWNED"
    assert client.get(f"/api/v1/assets/{asset['id']}/file").content == b"RIFFexample"
    queued = client.post(f"/api/v1/assets/{asset['id']}/transcribe")
    assert queued.status_code == 202
    assert client.post(f"/api/v1/assets/{asset['id']}/transcribe").status_code == 409
    assert client.get(f"/api/v1/assets/{asset['id']}/transcript").status_code == 404


def test_local_api_rejects_foreign_browser_origin(client: TestClient) -> None:
    assert (
        client.post("/api/v1/assets", headers={"origin": "https://foreign.example"}).status_code
        == 403
    )


def test_local_panel_origin_uses_configured_web_port(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_local_web_port", 3180)
    response = client.post(
        "/api/v1/channels",
        headers={"origin": "http://127.0.0.1:3180"},
        json={
            "name": "Canal de prova", "slug": "canal-de-prova", "niche": "Ficcao",
            "default_engine": "football",
        },
    )
    assert response.status_code == 201, response.text
    assert client.post(
        "/api/v1/channels", headers={"origin": "http://127.0.0.1:3000"},
        json={},
    ).status_code == 403


def test_voice_job_is_queued_and_failed_cleanly_without_windows(
    client: TestClient, monkeypatch
) -> None:
    channel = client.post(
        "/api/v1/channels",
        json={"name": "Canal", "slug": "canal", "niche": "Geo", "default_engine": "geo"},
    ).json()
    project = client.post(
        "/api/v1/projects",
        json={"channel_id": channel["id"], "title": "Mapa", "topic": "Mapa do mundo"},
    ).json()
    assert client.post(f"/api/v1/projects/{project['id']}/voice").status_code == 409
    plan = client.post(f"/api/v1/projects/{project['id']}/plan").json()
    assert client.post(f"/api/v1/projects/{project['id']}/voice").status_code == 409
    for index, scene in enumerate(plan["scenes"]):
        scene["narration"] = f"Cena {index + 1} revisada para gerar voz."
    client.put(
        f"/api/v1/projects/{project['id']}/plan",
        json={"hook": plan["hook"], "angle": plan["angle"], "scenes": plan["scenes"]},
    )
    queued = client.post(f"/api/v1/projects/{project['id']}/voice")
    assert queued.status_code == 202
    monkeypatch.setattr(
        "workers.render.main.synthesize_voice",
        lambda *_: (_ for _ in ()).throw(RuntimeError("Offline speech unavailable")),
    )
    assert media_one()
    job = client.get(f"/api/v1/jobs/{queued.json()['job_id']}").json()
    assert job["status"] == "FAILED"
    assert "Offline speech" in job["error"]


def test_ollama_is_restricted_to_loopback(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://external.example")
    get_settings.cache_clear()
    try:
        assert local_ollama_url() is None
        with SessionLocal() as db:
            channel = Channel(name="Canal", slug="canal", niche="Geo", default_engine="geo")
            db.add(channel)
            db.flush()
            project = Project(channel_id=channel.id, title="Mapa", topic="Mapa do mundo")
            db.add(project)
            db.flush()
            plan = build_local_plan(project, channel)
            assert enrich_plan_with_local_ai(plan, project.topic) == plan
    finally:
        get_settings.cache_clear()


def test_local_database_backup(client: TestClient) -> None:
    backup_local_database()
    assert list((Path("data") / "backups").glob("mediagrid-*.db"))


def test_backup_file_lock_does_not_stop_worker(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)

    def locked_destination(*_args: object) -> None:
        raise PermissionError("backup destination is locked")

    monkeypatch.setattr("workers.render.main.os.replace", locked_destination)
    backup_local_database()
    assert not list((tmp_path / "backups").iterdir())


def test_voice_is_invalidated_when_script_changes(client: TestClient) -> None:
    channel = client.post(
        "/api/v1/channels",
        json={"name": "Canal", "slug": "canal", "niche": "Geo", "default_engine": "geo"},
    ).json()
    project = client.post(
        "/api/v1/projects",
        json={"channel_id": channel["id"], "title": "Mapa", "topic": "Mapa do mundo"},
    ).json()
    plan = client.post(f"/api/v1/projects/{project['id']}/plan").json()
    folder = get_settings().mediagrid_data_dir / "voice"
    folder.mkdir(exist_ok=True)
    audio = folder / f"{project['id']}.wav"
    manifest = folder / f"{project['id']}.sha256"
    audio.write_bytes(b"RIFFsample")
    with SessionLocal() as db:
        record = db.get(Project, project["id"])
        assert record
        manifest.write_text(hashlib.sha256(narration_text(record.script).encode()).hexdigest())
    assert client.get(f"/api/v1/projects/{project['id']}").json()["voice_ready"]
    plan["scenes"][0]["narration"] = "Texto novo para esta cena"
    response = client.put(
        f"/api/v1/projects/{project['id']}/plan",
        json={"hook": "Nova abertura", "angle": plan["angle"], "scenes": plan["scenes"]},
    )
    assert response.json()["voice_ready"] is False
    assert client.get(f"/api/v1/projects/{project['id']}/voice").status_code == 404


def test_new_voice_manifest_detects_changed_wav(client: TestClient) -> None:
    folder = get_settings().mediagrid_data_dir / "voice"
    folder.mkdir(exist_ok=True)
    project_id = "voice-hash-fixture"
    script = {"segments": ["Uma frase de teste"]}
    audio = folder / f"{project_id}.wav"
    manifest = folder / f"{project_id}.sha256"
    audio.write_bytes(b"RIFForiginal")
    script_hash = hashlib.sha256(narration_text(script).encode()).hexdigest()
    audio_hash = hashlib.sha256(audio.read_bytes()).hexdigest()
    manifest.write_text(f"{script_hash} {audio_hash}")
    assert voice_matches(project_id, script)
    audio.write_bytes(b"RIFFchanged")
    assert not voice_matches(project_id, script)
