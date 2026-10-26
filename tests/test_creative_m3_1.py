"""M3.1 contract regressions. Encoder-independent tests, real render QA in proof scripts."""

import wave

import pytest
from test_creative_m3 import foundation

from apps.api.creative.motion import verify_motion
from apps.api.database import SessionLocal
from apps.api.models import Asset, Job, Project


def refined(client, tmp_path, monkeypatch):
    project, root, request = foundation(client, tmp_path, monkeypatch)
    path = tmp_path / "new.wav"
    with wave.open(str(path), "wb") as target:
        target.setparams((1, 2, 48000, 576000, "NONE", "not compressed"))
        target.writeframes(b"\x01\x00"*576000)
    with path.open("rb") as source:
        response = client.post("/api/v1/assets",
            files={"file": ("new.wav", source, "audio/wav")},
            data={"rights_status": "OWNED", "commercial_use": "true"})
    assert response.status_code == 201, response.text
    request.update(art_direction="editorial", sound_design_asset_id=response.json()["id"])
    return project, root, request


def test_variants_bind_distinct_plans_to_same_approved_snapshot(client, tmp_path, monkeypatch):
    project, root, request = refined(client, tmp_path, monkeypatch)
    before = client.get(root+"/review").json()
    results = []
    for variant in ("editorial", "broadcast", "broadcast_final"):
        request["art_direction"] = variant
        preview = client.post(root+"/motion/preview", json=request)
        assert preview.status_code == 200, preview.text
        plan = preview.json()["plan"]
        assert plan["approved_snapshot_sha256"] == before["current_snapshot_sha256"]
        assert len(plan["assets"]) == 2
        assert plan["assets"][0]["role"] == "approved_soundtrack"
        assert plan["assets"][1]["role"] == "derived_sound_design"
        sound = preview.json()["props"]["sounds"][0]
        assert sound["media_file"] == request["sound_design_asset_id"]
        assert all(o["art_direction"] == variant and not o["diagnostics"]
                   for o in preview.json()["props"]["overlays"])
        job = client.post(root+"/motion/render", json=request).json()
        assert client.post(root+"/motion/render", json=request).json()["id"] == job["id"]
        results.append(job["id"])
        with SessionLocal() as db:
            verify_motion(db, project, db.get(Job, job["id"]).payload)
            row = db.get(Project, project)
            assert row.edl is None and row.plan is None and row.script is None
    assert len(set(results)) == 3
    assert client.get(root+"/review").json() == before


def test_diagnostics_are_explicit_and_change_the_plan_hash(client, tmp_path, monkeypatch):
    _, root, request = refined(client, tmp_path, monkeypatch)
    clean = client.post(root+"/motion/preview", json=request).json()
    diagnostic = client.post(root+"/motion/preview", json=dict(request, diagnostics=True)).json()
    assert clean["plan_sha256"] != diagnostic["plan_sha256"]
    assert all(o["diagnostics"] for o in diagnostic["props"]["overlays"])


@pytest.mark.parametrize("change", [
    {"art_direction": "unknown"},
    {"art_direction": "original"},
    {"sound_design_asset_id": None},
])
def test_invalid_variant_contracts_rejected(client, tmp_path, monkeypatch, change):
    _, root, request = refined(client, tmp_path, monkeypatch)
    assert client.post(root+"/motion/render", json=dict(request, **change)).status_code == 422


def test_new_audio_tampering_preserves_storyboard_but_blocks_render(client, tmp_path, monkeypatch):
    project, root, request = refined(client, tmp_path, monkeypatch)
    job = client.post(root+"/motion/render", json=request).json()
    (tmp_path/"assets"/request["sound_design_asset_id"]).write_bytes(b"tampered")
    assert client.post(root+"/motion/preview", json=request).status_code == 409
    assert client.get(root+"/review").json()["status"] == "APPROVED_STORYBOARD"
    with SessionLocal() as db, pytest.raises(ValueError, match="SHA-256 changed"):
        verify_motion(db, project, db.get(Job, job["id"]).payload)


def test_new_audio_rights_are_checked(client, tmp_path, monkeypatch):
    _, root, request = refined(client, tmp_path, monkeypatch)
    with SessionLocal() as db:
        asset = db.get(Asset, request["sound_design_asset_id"])
        asset.commercial_use = False
        db.commit()
    assert client.post(root+"/motion/render", json=request).status_code == 409
    assert client.get(root+"/review").json()["status"] == "APPROVED_STORYBOARD"

