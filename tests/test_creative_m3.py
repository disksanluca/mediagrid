"""M3 approval, immutable derivation, idempotence and worker gates; no fake media QA."""

import copy
import wave
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from apps.api.config import get_settings
from apps.api.creative.motion import verify_motion
from apps.api.database import SessionLocal
from apps.api.main import app
from apps.api.models import Job, Project
from scripts.proof_creative_motion import DNA, SHOTS
from workers.render import main as worker


def foundation(client, tmp_path, monkeypatch, approve=True):
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    wav = tmp_path / "score.wav"
    with wave.open(str(wav), "wb") as target:
        target.setparams((1, 2, 48000, 576000, "NONE", "not compressed"))
        target.writeframes(b"\x00\x00" * 576000)
    channel = client.post(
        "/api/v1/channels",
        json={
            "name": "Sports proof",
            "slug": "sports-proof",
            "niche": "Sports",
            "default_engine": "football",
        },
    ).json()
    project = client.post(
        "/api/v1/projects",
        json={"channel_id": channel["id"], "title": "Original sports", "topic": "Fictional sports"},
    ).json()
    with wav.open("rb") as source:
        response = client.post(
            "/api/v1/assets",
            files={"file": ("score.wav", source, "audio/wav")},
            data={"rights_status": "OWNED", "commercial_use": "true"},
        )
    assert response.status_code == 201, response.text
    asset = response.json()
    root = f"/api/v1/projects/{project['id']}/creative"
    assert (
        client.put(
            f"/api/v1/channels/{channel['id']}/creative-dna",
            json={"expected_revision": 0, "content": DNA},
        ).status_code
        == 200
    )
    assert (
        client.put(
            root + "/brief",
            json={
                "expected_revision": 0,
                "content": {
                    "topic": "Original fictional sports",
                    "audience": "Sports viewers",
                    "objective": "Test motion and sound",
                    "duration_ms": 12000,
                    "fps": 30,
                    "factual_mode": "FICTIONAL",
                    "asset_ids": [asset["id"]],
                },
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            root + "/directions",
            json={"expected_revision": 0, "expected_brief_revision": 1, "expected_dna_revision": 1},
        ).status_code
        == 200
    )
    response = client.put(
        root + "/storyboard",
        json={
            "expected_revision": 0,
            "expected_direction_revision": 1,
            "content": {
                "direction_id": "evidence-led",
                "duration_ms": 12000,
                "fps": 30,
                "shots": [dict(shot, asset_ids=[asset["id"]]) for shot in SHOTS],
            },
        },
    )
    assert response.status_code == 200, response.text
    snapshot = client.get(root + "/review").json()["current_snapshot_sha256"]
    if approve:
        response = client.post(
            root + "/decision",
            json={
                "expected_revision": 0,
                "expected_storyboard_revision": 1,
                "expected_snapshot_sha256": snapshot,
                "decision": "APPROVE",
                "actor": "Test operator",
                "storyboard_reviewed": True,
                "rights_checked": True,
                "facts_checked": True,
            },
        )
        assert response.status_code == 200, response.text
    return (
        project["id"],
        root,
        {
            "expected_snapshot_sha256": snapshot,
            "expected_storyboard_revision": 1,
            "soundtrack_asset_id": asset["id"],
            "quality": "preview",
        },
    )


def test_motion_derivation_preserves_approval_and_legacy_state(client, tmp_path, monkeypatch):
    project_id, root, request = foundation(client, tmp_path, monkeypatch)
    preview = client.post(root + "/motion/preview", json=request)
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert len(data["props"]["overlays"]) == 4
    assert [s["duration"] for s in data["props"]["scenes"]] == [2, 3, 4, 3]
    assert data["props"]["sounds"][0]["media_file"] == request["soundtrack_asset_id"]
    first = client.post(root + "/motion/render", json=request)
    assert first.status_code == 202, first.text
    assert client.post(root + "/motion/render", json=request).json()["id"] == first.json()["id"]
    assert client.get(root + "/review").json()["status"] == "APPROVED_STORYBOARD"
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        assert project.edl is None and project.plan is None and project.script is None
        job = db.get(Job, first.json()["id"])
        assert job.payload["plan_sha256"] == data["plan_sha256"]
        assert verify_motion(db, project_id, job.payload)["storyboard"]["revision"] == 1
    with TestClient(app) as restarted:
        assert restarted.get(f"/api/v1/jobs/{first.json()['id']}").json()["status"] == "QUEUED"
        assert restarted.get(root + "/review").json()["status"] == "APPROVED_STORYBOARD"


def test_motion_queue_is_concurrently_idempotent(client, tmp_path, monkeypatch):
    _, root, request = foundation(client, tmp_path, monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: client.post(root + "/motion/render", json=request), range(2))
        )
    assert [r.status_code for r in results] == [202, 202]
    assert results[0].json()["id"] == results[1].json()["id"]


def test_motion_requires_approval_and_strict_request(client, tmp_path, monkeypatch):
    _, root, request = foundation(client, tmp_path, monkeypatch, approve=False)
    assert client.post(root + "/motion/preview", json=request).status_code == 409
    assert client.post(root + "/motion/render", json=request).status_code == 409
    assert client.post(root + "/motion/render", json=dict(request, extra=True)).status_code == 422


def test_stale_job_fails_before_renderer_and_does_not_change_project(client, tmp_path, monkeypatch):
    project_id, root, request = foundation(client, tmp_path, monkeypatch)
    job = client.post(root + "/motion/render", json=request).json()
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        project.plan = {"origin": "MANUAL", "scenes": []}
        db.commit()

    def unexpected(*args, **kwargs):
        pytest.fail("Renderer must not run for stale input")

    monkeypatch.setattr("workers.render.creative_motion.render_remotion", unexpected)
    assert worker.media_one()
    result = client.get(f"/api/v1/jobs/{job['id']}").json()
    assert result["status"] == "FAILED" and "approved storyboard" in result["error"]
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        assert project.status == "IDEA" and project.edl is None
    assert client.get(root + f"/motion/jobs/{job['id']}/video").status_code == 409


def test_physical_hash_and_payload_tamper_are_blocked(client, tmp_path, monkeypatch):
    project_id, root, request = foundation(client, tmp_path, monkeypatch)
    job = client.post(root + "/motion/render", json=request).json()
    with SessionLocal() as db:
        row = db.get(Job, job["id"])
        changed = copy.deepcopy(row.payload)
        changed["plan"]["render"]["frames"] = 1
        with pytest.raises(ValueError, match="hash mismatch"):
            verify_motion(db, project_id, changed)
    (tmp_path / "assets" / request["soundtrack_asset_id"]).write_bytes(b"modified")
    assert client.post(root + "/motion/preview", json=request).status_code == 409
    assert worker.media_one()
    assert client.get(f"/api/v1/jobs/{job['id']}").json()["status"] == "FAILED"


def test_preset_contract_rejects_unreadable_text(client, tmp_path, monkeypatch):
    _, root, request = foundation(client, tmp_path, monkeypatch)
    board = client.get(root + "/storyboard").json()["content"]
    board["shots"][0]["on_screen_text"] = "A" * 40
    assert (
        client.put(
            root + "/storyboard",
            json={"expected_revision": 1, "expected_direction_revision": 1, "content": board},
        ).status_code
        == 200
    )
    state = client.get(root + "/review").json()
    response = client.post(
        root + "/decision",
        json={
            "expected_revision": 1,
            "expected_storyboard_revision": 2,
            "expected_snapshot_sha256": state["current_snapshot_sha256"],
            "decision": "APPROVE",
            "actor": "Test operator",
            "storyboard_reviewed": True,
            "rights_checked": True,
            "facts_checked": True,
        },
    )
    assert response.status_code == 200
    request.update(
        expected_storyboard_revision=2, expected_snapshot_sha256=state["current_snapshot_sha256"]
    )
    assert client.post(root + "/motion/preview", json=request).status_code == 422


def test_change_during_encoding_discards_artifact(client, tmp_path, monkeypatch):
    """An encoder stub tests orchestration only; real codec QA lives in the proof script."""
    project_id, root, request = foundation(client, tmp_path, monkeypatch)
    queued = client.post(root + "/motion/render", json=request).json()
    legacy = tmp_path / "renders" / f"{project_id}.mp4"
    legacy.parent.mkdir(exist_ok=True)
    legacy.write_bytes(b"existing legacy artifact")

    def encode_then_edit(props_path, public_dir, output, **kwargs):
        output.write_bytes(b"staged output, not a real MP4")
        with SessionLocal() as other:
            project = other.get(Project, project_id)
            project.topic = "Changed during the render"
            other.commit()

    monkeypatch.setattr("workers.render.creative_motion.render_remotion", encode_then_edit)
    monkeypatch.setattr("workers.render.creative_motion.validate_motion_video", lambda *_: {})
    assert worker.media_one()
    finished = client.get(f"/api/v1/jobs/{queued['id']}").json()
    assert finished["status"] == "FAILED" and "approved storyboard" in finished["error"]
    assert not (tmp_path / "creative-renders" / f"{queued['id']}.mp4").exists()
    assert not list((tmp_path / "temp").glob("media-*.mp4"))
    assert legacy.read_bytes() == b"existing legacy artifact"


def test_existing_project_edl_is_preserved(client, tmp_path, monkeypatch):
    project_id, root, request = foundation(client, tmp_path, monkeypatch, approve=False)
    original = {"version": 1, "tracks": {"video": [{"scene_id": "legacy", "duration": 5}]}}
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        project.edl = original
        project.plan = {"origin": "MANUAL", "note": "Existing user plan"}
        project.script = {"segments": ["Existing user script"]}
        db.commit()
    snapshot = client.get(root + "/review").json()["current_snapshot_sha256"]
    approved = client.post(root + "/decision", json={
        "expected_revision": 0, "expected_storyboard_revision": 1,
        "expected_snapshot_sha256": snapshot, "decision": "APPROVE", "actor": "Test operator",
        "storyboard_reviewed": True, "rights_checked": True, "facts_checked": True,
    })
    assert approved.status_code == 200
    request["expected_snapshot_sha256"] = snapshot
    assert client.post(root + "/motion/render", json=request).status_code == 202
    assert client.get(root + "/review").json()["status"] == "APPROVED_STORYBOARD"
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        assert project.edl == original
        assert project.plan == {"origin": "MANUAL", "note": "Existing user plan"}
        assert project.script == {"segments": ["Existing user script"]}
