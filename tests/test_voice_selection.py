"""A chosen Windows voice must be persisted and bound to the produced WAV."""

import hashlib
import json

from fastapi.testclient import TestClient

from apps.api.config import get_settings
from apps.api.local_media import voice_configuration_digest, voice_matches
from workers.render.main import media_one


def test_voice_choice_and_retry_follow_current_local_configuration(
    client: TestClient, monkeypatch, tmp_path,
) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    voices = ("Maria pt-BR", "Daniel pt-BR")
    monkeypatch.setattr("apps.api.local_media.installed_portuguese_voices", lambda: voices)
    monkeypatch.setattr("apps.api.routes.system.installed_portuguese_voices", lambda: voices)
    initial = client.get("/api/v1/system/voice")
    assert initial.status_code == 200
    assert initial.json()["voices"] == list(voices)
    assert client.put("/api/v1/system/voice", json={
        "voice_name": "en-US voice", "rate": 0,
    }).status_code == 422
    assert client.put("/api/v1/system/voice", json={
        "voice_name": voices[0], "rate": 6,
    }).status_code == 422
    saved = client.put("/api/v1/system/voice", json={
        "voice_name": voices[0], "rate": -1,
    })
    assert saved.status_code == 200
    assert saved.json()["voice_name"] == voices[0]
    assert json.loads((tmp_path / "settings.json").read_text())["voice_rate"] == -1

    channel = client.post("/api/v1/channels", json={
        "name": "Voz", "slug": "voz", "niche": "Teste", "default_engine": "music",
    }).json()
    project = client.post("/api/v1/projects", json={
        "channel_id": channel["id"], "title": "Narração configurável",
        "topic": "\n".join((
            "Primeiro trecho revisado para gerar uma voz local.",
            "Segundo trecho com duração e conteúdo próprios.",
            "Terceiro trecho encerra este teste de narração.",
        )),
    }).json()
    assert client.post(f"/api/v1/projects/{project['id']}/plan").status_code == 200
    queued = client.post(f"/api/v1/projects/{project['id']}/voice").json()
    first_digest = voice_configuration_digest()
    assert queued["status"] == "QUEUED"

    assert client.put("/api/v1/system/voice", json={
        "voice_name": voices[1], "rate": 1,
    }).status_code == 200
    assert voice_configuration_digest() != first_digest
    assert media_one()
    failed = client.get(f"/api/v1/jobs/{queued['job_id']}").json()
    assert failed["status"] == "FAILED"
    assert "Voice selection changed" in failed["error"]

    def fake_speech(_text, output):
        output.write_bytes(b"RIFFchosen-voice")

    monkeypatch.setattr("workers.render.main.synthesize_voice", fake_speech)
    retry = client.post(f"/api/v1/jobs/{queued['job_id']}/retry")
    assert retry.status_code == 200
    assert retry.json()["status"] == "QUEUED"
    assert media_one()
    completed = client.get(f"/api/v1/jobs/{queued['job_id']}").json()
    assert completed["status"] == "SUCCEEDED", completed["error"]
    manifest = (tmp_path / "voice" / f"{project['id']}.sha256").read_text().split()
    assert len(manifest) == 3
    assert manifest[1] == hashlib.sha256(b"RIFFchosen-voice").hexdigest()
    assert manifest[2] == voice_configuration_digest()
    script = client.get(f"/api/v1/projects/{project['id']}").json()["script"]
    assert voice_matches(project["id"], script)
    assert client.put("/api/v1/system/voice", json={
        "voice_name": voices[0], "rate": 0,
    }).status_code == 200
    assert not voice_matches(project["id"], script)
