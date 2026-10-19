import wave
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.database import SessionLocal
from apps.api.models import Project, ProjectStatus
from workers.render.main import fit_video_to_voice


def test_render_extends_scenes_when_voice_exceeds_planned_duration(tmp_path: Path) -> None:
    voice = tmp_path / "narration.wav"
    with wave.open(str(voice), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(100)
        wav.writeframes(b"\0\0" * 4500)
    original = [
        {"scene_id": "a", "duration": 7},
        {"scene_id": "b", "duration": 22},
        {"scene_id": "c", "duration": 6},
    ]
    audio = [
        {"scene_id": "a", "text": "short introduction"},
        {"scene_id": "b", "text": "a longer ementa with many words to read aloud"},
        {"scene_id": "c", "text": "closing line"},
    ]
    fitted, duration = fit_video_to_voice(original, audio, voice)
    assert duration >= 46
    assert fitted[1]["duration"] > original[1]["duration"]
    assert fitted[1]["duration"] - original[1]["duration"] > (
        fitted[0]["duration"] - original[0]["duration"]
    )
    assert original[1]["duration"] == 22


def test_new_voice_revokes_approval_and_hides_stale_output(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    from apps.api.config import get_settings

    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    channel = client.post(
        "/api/v1/channels",
        json={
            "name": "Política",
            "slug": "politica",
            "niche": "Política",
            "default_engine": "politics",
        },
    ).json()
    project = client.post(
        "/api/v1/projects",
        json={
            "channel_id": channel["id"],
            "title": "Plano com fontes",
            "topic": "Primeiro fato concreto com mais de vinte caracteres.\n"
            "Segundo fato concreto com mais de vinte caracteres.\n"
            "Terceiro fato concreto com mais de vinte caracteres.",
        },
    ).json()
    project_id = project["id"]
    client.post(f"/api/v1/projects/{project_id}/plan")
    with SessionLocal() as db:
        stored = db.get(Project, project_id)
        assert stored is not None
        stored.status = ProjectStatus.QC.value
        db.commit()
    render_dir = tmp_path / "renders"
    render_dir.mkdir()
    (render_dir / f"{project_id}.mp4").write_bytes(b"old-render")
    assert client.post(
        f"/api/v1/projects/{project_id}/review",
        json={
            "source_urls": ["https://www.camara.leg.br/"],
            "facts_confirmed": True,
            "rights_confirmed": True,
            "notes": "Conferido na Câmara",
        },
    ).status_code == 200
    assert client.post(f"/api/v1/projects/{project_id}/voice").status_code == 202
    assert client.post(f"/api/v1/projects/{project_id}/render").status_code == 409
    refreshed = client.get(f"/api/v1/projects/{project_id}").json()
    assert refreshed["status"] == "SCRIPTED"
    assert "review" not in refreshed["plan"]
    assert client.get(f"/api/v1/projects/{project_id}/output").status_code == 404
    assert client.get(f"/api/v1/projects/{project_id}/export").status_code == 409
