import hashlib
import io
import math
import os
import shutil
import struct
import subprocess
import wave

import pytest
from fastapi.testclient import TestClient

from apps.api.config import get_settings
from apps.api.database import SessionLocal
from apps.api.local_media import voice_matches
from apps.api.models import Event, Job, JobStatus, Project, ProjectStatus


def _tone(frequency: int = 220) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"".join(
            struct.pack("<h", int(6500 * math.sin(2 * math.pi * frequency * index / 16000)))
            for index in range(16000)
        ))
    return buffer.getvalue()


def _project(client: TestClient) -> tuple[str, dict]:
    channel = client.post("/api/v1/channels", json={
        "name": "Voz própria", "slug": "voz-propria", "niche": "Geo", "default_engine": "geo",
    }).json()
    project = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Narração", "topic": "Mapa do mundo",
    }).json()
    plan = client.post(f"/api/v1/projects/{project['id']}/plan").json()
    for index, scene in enumerate(plan["scenes"]):
        scene["narration"] = f"Cena {index + 1} com narração conferida."
    saved = client.put(f"/api/v1/projects/{project['id']}/plan", json={
        "hook": plan["hook"], "angle": plan["angle"], "scenes": plan["scenes"],
    })
    assert saved.status_code == 200
    return project["id"], saved.json()["plan"]


def _upload(client: TestClient, project_id: str, content: bytes, *,
            rights: str = "true", script: str = "true",
            filename: str = "my-narration.wav", media_type: str = "audio/wav"):
    return client.post(f"/api/v1/projects/{project_id}/voice/recorded", files={
        "file": (filename, content, media_type),
    }, data={"rights_confirmed": rights, "script_confirmed": script})


def test_recorded_voice_requires_attestations_and_valid_audio(
    client: TestClient, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    project_id, _ = _project(client)
    tone = _tone()
    assert _upload(client, project_id, tone, rights="false").status_code == 422
    assert _upload(client, project_id, tone, script="false").status_code == 422
    assert _upload(client, project_id, b"not audio").status_code == 422
    assert not (tmp_path / "voice" / f"{project_id}.wav").exists()


def test_owned_recording_is_hashed_used_and_invalidated_on_script_edit(
    client: TestClient, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    project_id, plan = _project(client)
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        assert project
        project.plan = {**(project.plan or {}), "review": {"notes": "previous approval"}}
        project.status = ProjectStatus.APPROVED.value
        db.commit()
    result = _upload(client, project_id, _tone())
    assert result.status_code == 200, result.text
    assert result.json()["status"] == ProjectStatus.SCRIPTED.value
    assert result.json()["voice_ready"] is True
    assert "review" not in result.json()["plan"]
    assert client.get(f"/api/v1/projects/{project_id}/voice").status_code == 200
    wav = tmp_path / "voice" / f"{project_id}.wav"
    manifest = (tmp_path / "voice" / f"{project_id}.sha256").read_text().split()
    assert manifest[1] == hashlib.sha256(wav.read_bytes()).hexdigest()
    assert manifest[2] == "RECORDED"
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        assert project and voice_matches(project_id, project.script)
        events = db.query(Event).filter(Event.entity_id == project_id).all()
        imported = next(event for event in events if event.event_type == "RECORDED_VOICE_IMPORTED")
        assert imported.after["rights_status"] == "RIGHTS_CONFIRMED"
        assert imported.after["script_match"] == "HUMAN_CONFIRMED"
        assert any(event.event_type == "PROJECT_APPROVAL_REVOKED" for event in events)
    (tmp_path / "settings.json").write_text('{"voice_name":"other"}')
    assert client.get(f"/api/v1/projects/{project_id}").json()["voice_ready"] is True
    plan["scenes"][0]["narration"] = "Roteiro alterado depois da gravação."
    changed = client.put(f"/api/v1/projects/{project_id}/plan", json={
        "hook": plan["hook"], "angle": plan["angle"], "scenes": plan["scenes"],
    })
    assert changed.status_code == 200
    assert changed.json()["voice_ready"] is False
    assert client.get(f"/api/v1/projects/{project_id}/voice").status_code == 404


def test_manifest_write_failure_restores_previous_voice(
    client: TestClient, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    project_id, _ = _project(client)
    assert _upload(client, project_id, _tone()).status_code == 200
    original = (tmp_path / "voice" / f"{project_id}.wav").read_bytes()
    replace = os.replace

    def fail_manifest(source, destination):
        if str(source).endswith(".sha256"):
            raise PermissionError("manifest locked")
        return replace(source, destination)

    monkeypatch.setattr("apps.api.routes.projects.os.replace", fail_manifest)
    response = _upload(client, project_id, _tone(330))
    assert response.status_code == 409
    assert (tmp_path / "voice" / f"{project_id}.wav").read_bytes() == original
    assert client.get(f"/api/v1/projects/{project_id}").json()["voice_ready"] is True


def test_recording_does_not_replace_active_voice_job(
    client: TestClient, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    project_id, _ = _project(client)
    with SessionLocal() as db:
        db.add(Job(project_id=project_id, job_type="VOICE", status=JobStatus.QUEUED.value))
        db.commit()
    assert _upload(client, project_id, _tone()).status_code == 409
    assert not (tmp_path / "voice" / f"{project_id}.wav").exists()


def test_locked_previous_wav_returns_actionable_error(
    client: TestClient, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    project_id, _ = _project(client)
    first = _upload(client, project_id, _tone())
    assert first.status_code == 200
    original = (tmp_path / "voice" / f"{project_id}.wav").read_bytes()

    def locked(*_args):
        raise PermissionError("locked by playback")

    monkeypatch.setattr("apps.api.routes.projects.os.replace", locked)
    response = _upload(client, project_id, _tone())
    assert response.status_code == 409
    assert "Feche a reprodução" in response.json()["detail"]
    assert (tmp_path / "voice" / f"{project_id}.wav").read_bytes() == original
    assert client.get(f"/api/v1/projects/{project_id}").json()["voice_ready"] is True


def test_browser_webm_opus_recording_is_normalized(
    client: TestClient, monkeypatch, tmp_path
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("FFmpeg is unavailable for WebM fixture")
    source = tmp_path / "source.wav"
    source.write_bytes(_tone())
    encoded = subprocess.run(
        [ffmpeg, "-nostdin", "-v", "error", "-y", "-i", str(source),
         "-c:a", "libopus", "-f", "webm", "pipe:1"], capture_output=True,
    )
    if encoded.returncode:
        pytest.skip("Local FFmpeg lacks the Opus encoder for WebM fixture")
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    project_id, _ = _project(client)
    response = _upload(client, project_id, encoded.stdout,
                       filename="microphone.webm", media_type="audio/webm")
    assert response.status_code == 200, response.text
    assert response.json()["voice_ready"] is True
    with wave.open(str(tmp_path / "voice" / f"{project_id}.wav"), "rb") as audio:
        assert audio.getframerate() == 48000
        assert audio.getnchannels() == 1
