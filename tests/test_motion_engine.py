"""M4 integrated contracts/API gates. Encoded audiovisual evidence is in proof_motion_engine."""

import copy
import hashlib
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.config import get_settings
from apps.api.creative.engine import instantiate
from apps.api.creative.hashing import content_sha256
from apps.api.creative.motion import motion_output, motion_props, verify_motion
from apps.api.database import SessionLocal
from apps.api.main import app
from apps.api.models import Asset, Job, MotionArtifactReview, Project
from apps.api.motion_contracts.fonts import layout_text
from apps.api.motion_contracts.models import MotionScene
from apps.api.motion_contracts.registry import load_recipe
from scripts.build_motion_recipes import PRODUCTIONS
from scripts.proof_motion_engine import seed_project


@pytest.fixture
def engine_project(client, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "mediagrid_data_dir", tmp_path)
    sound = tmp_path / "test.wav"
    with wave.open(str(sound), "wb") as target:
        target.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
        target.writeframes(b"\0" * 48000 * 12 * 4)
    project, root, request = seed_project(client, "sports", {"score": (sound, "audio/wav")})
    return project["id"], root, request


def prepare(client, fixture):
    _, root, request = fixture
    response = client.post(root + "/motion/engine/preview", json=request)
    assert response.status_code == 200, response.text
    return response.json()


def artifact_fixture(client, fixture):
    _, root, request = fixture
    job = client.post(root + "/motion/engine/render", json=request).json()
    assert job["motion_schema"] == "creative_motion_engine_v1"
    # This fake payload tests review/hash gates only, never video validity or artistic quality.
    video = b"unit-test-artifact-hash-only"
    path = motion_output(job["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(video)
    with SessionLocal() as db:
        row = db.get(Job, job["id"])
        digest = row.payload["plan_sha256"]
        row.status = "SUCCEEDED"
        row.result = {"sha256": hashlib.sha256(video).hexdigest(), "plan_sha256": digest}
        db.commit()
    request = {
        "expected_revision": 0,
        "expected_plan_sha256": digest,
        "expected_video_sha256": hashlib.sha256(video).hexdigest(),
        "decision": "APPROVE",
        "notes": "Unit test; no human approval asserted",
        "video_watched": True,
        "audio_checked": True,
        "rights_checked": True,
    }
    return root + f"/motion/jobs/{job['id']}", request, path


def test_engine_preview_is_deterministic_and_does_not_mutate_project(client, engine_project):
    project_id, root, _ = engine_project
    with SessionLocal() as db:
        row = db.get(Project, project_id)
        before = copy.deepcopy((row.edl, row.plan, row.script))
    a, b = prepare(client, engine_project), prepare(client, engine_project)
    assert a == b
    assert content_sha256(a["plan"]) == a["plan_sha256"]
    props = motion_props(a["plan"])
    props["overlays"][0]["motion"]["assets"].clear()
    assert content_sha256(a["plan"]) == a["plan_sha256"]
    assert a["props"]["overlays"][0]["preset"] == "motion_scene_v1"
    assert a["plan"]["render"]["frames"] == 360
    assert client.get(root + "/review").json()["status"] == "APPROVED_STORYBOARD"
    with SessionLocal() as db:
        row = db.get(Project, project_id)
        assert before == (row.edl, row.plan, row.script)


@pytest.mark.parametrize(
    "field,value,status",
    [
        ("expected_storyboard_revision", 99, 409),
        ("expected_snapshot_sha256", "0" * 64, 409),
        ("quality", "4k", 422),
        ("script", "alert(1)", 422),
        ("parameters", {"text_scale": 9}, 422),
        ("asset_bindings", {"score": "../outside"}, 422),
        ("asset_bindings", {"score": "unregistered"}, 422),
    ],
)
def test_engine_rejects_invalid_or_stale_requests(client, engine_project, field, value, status):
    _, root, request = engine_project
    response = client.post(root + "/motion/engine/preview", json={**request, field: value})
    assert response.status_code == status, response.text


def test_concurrent_enqueue_is_idempotent(client, engine_project):
    project_id, root, request = engine_project

    def enqueue(_):
        response = client.post(root + "/motion/engine/render", json=request)
        assert response.status_code == 202, response.text
        return response.json()["id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(enqueue, range(2)))
    assert ids[0] == ids[1]
    with SessionLocal() as db:
        assert (
            db.query(Job).filter_by(project_id=project_id, job_type="CREATIVE_MOTION").count() == 1
        )


def test_changed_asset_blocks_queued_plan_and_preview(client, engine_project):
    project_id, root, request = engine_project
    job = client.post(root + "/motion/engine/render", json=request).json()
    asset_id = request["asset_bindings"]["score"]
    with (get_settings().mediagrid_data_dir / "assets" / asset_id).open("ab") as changed:
        changed.write(b"changed")
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="SHA-256"):
            verify_motion(db, project_id, db.get(Job, job["id"]).payload)
    assert client.post(root + "/motion/engine/preview", json=request).status_code == 422


def test_rights_revocation_obsoletes_approval(client, engine_project):
    _, root, request = engine_project
    with SessionLocal() as db:
        db.get(Asset, request["asset_bindings"]["score"]).commercial_use = False
        db.commit()
    assert client.post(root + "/motion/engine/render", json=request).status_code == 409


def test_recipe_and_runtime_hashes_are_verified(client, engine_project, monkeypatch):
    project_id, root, request = engine_project
    changed = copy.deepcopy(request)
    changed["recipe"]["sha256"] = "0" * 64
    assert client.post(root + "/motion/engine/preview", json=changed).status_code == 422
    result = prepare(client, engine_project)
    monkeypatch.setattr("apps.api.creative.engine.runtime_manifest", lambda: {"different": True})
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="changed"):
            verify_motion(
                db, project_id, {"plan": result["plan"], "plan_sha256": result["plan_sha256"]}
            )


def test_runtime_manifest_normalizes_module_path_alias(client, engine_project, monkeypatch):
    from apps.api.creative import engine

    expected = prepare(client, engine_project)
    source = Path(engine.__file__).resolve()
    # A lexical alias is portable; the frozen Windows executable can instead
    # receive an 8.3 alias. Both must resolve before relative manifest keys.
    alias = source.parent / ".." / source.parent.name / source.name
    monkeypatch.setattr(engine, "__file__", str(alias))
    actual = prepare(client, engine_project)
    assert actual == expected
    assert "creative/engine.py" in actual["plan"]["runtime"]["engine_files"]


def test_human_artifact_review_is_exact_idempotent_and_separate(client, engine_project):
    _, root, _ = engine_project
    endpoint, decision, path = artifact_fixture(client, engine_project)
    initial = client.get(endpoint + "/review").json()
    assert initial["status"] == "AWAITING_HUMAN_REVIEW"
    a = client.post(endpoint + "/review", json=decision)
    assert a.status_code == 200, a.text
    assert a.json()["status"] == "APPROVED_ARTIFACT"
    assert client.post(endpoint + "/review", json=decision).json()["revision"] == 1
    stale = client.post(endpoint + "/review", json={**decision, "decision": "REJECT"})
    assert stale.status_code == 409
    assert client.get(root + "/review").json()["status"] == "APPROVED_STORYBOARD"
    with SessionLocal() as db:
        assert db.query(MotionArtifactReview).count() == 1
        assert db.query(MotionArtifactReview).one().actor == "local-user"
    path.write_bytes(b"different exact artifact")
    assert client.get(endpoint + "/video").status_code == 409
    stale_review = client.get(endpoint + "/review").json()
    assert stale_review["status"] == "STALE" and stale_review["blockers"]
    assert stale_review["history"][0]["decision"] == "APPROVE"
    assert client.post(endpoint + "/review", json=decision).status_code == 409


def test_artifact_review_needs_matching_hash_and_confirmations(client, engine_project):
    endpoint, decision, _ = artifact_fixture(client, engine_project)
    for field, value, status in (
        ("expected_video_sha256", "0" * 64, 409),
        ("video_watched", False, 422),
        ("actor", "impersonation", 422),
    ):
        assert (
            client.post(endpoint + "/review", json={**decision, field: value}).status_code == status
        )


def test_concurrent_artifact_decisions_conflict(client, engine_project):
    endpoint, decision, _ = artifact_fixture(client, engine_project)

    def decide(value):
        return client.post(endpoint + "/review", json={**decision, "decision": value}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(decide, ["APPROVE", "REJECT"]))
    assert sorted(statuses) == [200, 409]


def test_different_project_cannot_review_or_access_artifact(client, engine_project):
    endpoint, decision, _ = artifact_fixture(client, engine_project)
    invalid = endpoint.replace(engine_project[0], "another-project")
    assert client.get(invalid + "/video").status_code == 404
    assert client.post(invalid + "/review", json=decision).status_code == 404


def test_existing_queue_cancel_and_retry_are_used(client, engine_project):
    _, root, request = engine_project
    job = client.post(root + "/motion/engine/render", json=request).json()
    cancelled = client.post(f"/api/v1/jobs/{job['id']}/cancel").json()
    assert cancelled["status"] == "CANCELLED"
    retried = client.post(f"/api/v1/jobs/{job['id']}/retry")
    assert retried.status_code == 200
    assert retried.json()["id"] == job["id"]


@pytest.mark.parametrize("label", list(PRODUCTIONS))
def test_production_recipes_share_contracts_but_have_different_structures(label):
    recipe = load_recipe(PRODUCTIONS[label]["id"], "1.1.0")
    for scene in recipe.scenes:
        assert MotionScene.model_validate(scene.graph.model_dump()) == scene.graph
    assert sum(s.required_duration_ms for s in recipe.scenes) == sum(
        PRODUCTIONS[label]["durations"]
    )


def test_recipe_retimes_to_approved_shots_without_second_timeline(client, engine_project):
    from apps.api.creative.contracts import CreativeStoryboard
    from apps.api.creative.engine import EngineParameters

    response = prepare(client, engine_project)
    board = copy.deepcopy(response["plan"]["storyboard"]["content"])
    board["shots"][0]["duration_ms"] += 100
    board["shots"][1]["start_ms"] += 100
    board["shots"][1]["duration_ms"] -= 100
    shots = CreativeStoryboard.model_validate(board).shots
    template = load_recipe("sports.depth-impact", "1.1.0")
    derived = instantiate(template, shots, EngineParameters())
    assert derived.scenes[0].required_duration_ms == 2100
    assert derived.scenes[1].graph.cues[0].sound.source_in_ms == 2100
    assert template.scenes[0].required_duration_ms == 2000
    assert derived.sha256 != template.sha256


def test_text_is_measured_and_missing_glyphs_rejected():
    wrapped, metrics = layout_text("ENTRE EM JOGO", 120, 400, 3)
    assert "\n" in wrapped and max(metrics["widths"]) <= 400
    with pytest.raises(ValueError, match="TEXT_OVERFLOW"):
        layout_text("EXCESSIVAMENTE", 400, 50, 1)
    with pytest.raises(ValueError, match="UNSUPPORTED_GLYPH"):
        layout_text("💥", 120, 900, 1)


def test_new_api_inherits_authentication(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "mediagrid_admin_password", "test-password")
    monkeypatch.setattr(settings, "mediagrid_session_secret", "test-secret")
    assert client.get("/api/v1/creative/motion/recipes").status_code == 401


def test_review_survives_session_restart(client, engine_project):
    endpoint, decision, _ = artifact_fixture(client, engine_project)
    assert client.post(endpoint + "/review", json=decision).status_code == 200
    with TestClient(app) as restarted:
        review = restarted.get(endpoint + "/review").json()
        assert review["status"] == "APPROVED_ARTIFACT"
        assert len(review["history"]) == 1
