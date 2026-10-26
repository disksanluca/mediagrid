"""Copy an approved disposable M3 proof, preserve its snapshot, render V1 and V2."""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.m3_1_score import create_score  # noqa: E402
from scripts.m3_2_score import create_score as create_polished_score  # noqa: E402
from scripts.proof_creative_motion import checked  # noqa: E402


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True, help="Existing disposable M3 proof")
    parser.add_argument("--run", required=True)
    parser.add_argument("--quality", choices=("preview", "final"), default="final")
    parser.add_argument("--polish-broadcast", action="store_true",
                        help="Render only the M3.2 final V2 in its own disposable directory")
    args = parser.parse_args()
    source = args.source.resolve()
    allowed = (ROOT / "data/creative-m3-proof").resolve()
    if not source.is_relative_to(allowed) or not (source / "proof.json").is_file():
        parser.error("Source must be a disposable M3 proof under data/creative-m3-proof")
    proof_area = "creative-m3-2-proof" if args.polish_broadcast else "creative-m3-1-proof"
    base = (ROOT / "data" / proof_area).resolve()
    folder = (base / args.run).resolve()
    if not folder.is_relative_to(base) or folder == base or folder.exists():
        parser.error(f"Use a new child directory under data/{proof_area}")
    previous = json.loads((source / "proof.json").read_text(encoding="utf-8"))
    source_db = source / "workspace.db"
    original_hash = hashlib.sha256(source_db.read_bytes()).hexdigest()
    folder.mkdir(parents=True)
    # SQLite's backup API captures a consistent copy; source is explicitly read-only.
    with sqlite3.connect(source_db.as_uri()+"?mode=ro", uri=True) as src:
        with sqlite3.connect(folder / "workspace.db") as dest:
            src.backup(dest)
    shutil.copytree(source / "assets", folder / "assets")
    os.environ.update({
        "DATABASE_URL": "sqlite:///" + (folder / "workspace.db").as_posix(),
        "MEDIAGRID_DATA_DIR": str(folder), "MEDIAGRID_MODE": "LOCAL",
        "ALLOW_PAID_AI": "false", "MEDIAGRID_RENDERER_ROOT": str(ROOT / "apps/renderer"),
        "MEDIAGRID_NODE_PATH": shutil.which("node") or "", "MEDIAGRID_RENDER_CONCURRENCY": "2",
    })
    from fastapi.testclient import TestClient

    from apps.api.database import SessionLocal
    from apps.api.main import app
    from apps.api.models import Job, Project
    from workers.render.main import media_one

    project_id = previous["project_id"]
    root = f"/api/v1/projects/{project_id}/creative"
    with TestClient(app) as client:
        approved = checked(client.get(root+"/review"))
        assert approved["status"] == "APPROVED_STORYBOARD"
        assert (
            approved["current_snapshot_sha256"]
            == previous["approval"]["current_snapshot_sha256"]
        )
        board = checked(client.get(root+"/storyboard"))
        assert board["sha256"] == previous["storyboard_sha256"]
        brief = checked(client.get(root+"/brief"))
        with SessionLocal() as db:
            project = db.get(Project, project_id)
            original = (project.edl, project.plan, project.script)
            assert not db.query(Job).filter(Job.status.in_(["QUEUED", "RUNNING"])).count()
        variants = (("v2", "broadcast_final"),) if args.polish_broadcast else (
            ("v1", "editorial"), ("v2", "broadcast"),
        )
        for name, variant in variants:
            output = folder / name
            output.mkdir()
            score = output / "original-score.wav"
            manifest = (create_polished_score(score) if args.polish_broadcast
                        else create_score(score, variant))
            write(output / "score-manifest.json", manifest)
            with score.open("rb") as audio:
                asset = checked(client.post("/api/v1/assets",
                    files={"file": (f"{variant}-original.wav", audio, "audio/wav")},
                    data={"rights_status": "OWNED", "commercial_use": "true",
                          "creator": f"MediaGrid original synthesis / {variant}",
                          "license_name": manifest["license"]}))
            request = {
                "expected_storyboard_revision": board["revision"],
                "expected_snapshot_sha256": approved["current_snapshot_sha256"],
                "soundtrack_asset_id": brief["content"]["asset_ids"][0],
                "sound_design_asset_id": asset["id"], "art_direction": variant,
                "diagnostics": False, "quality": args.quality,
            }
            preview = checked(client.post(root+"/motion/preview", json=request))
            write(output / "preview.json", preview)
            job = checked(client.post(root+"/motion/render", json=request))
            assert checked(client.post(root+"/motion/render", json=request))["id"] == job["id"]
            assert media_one(), "Worker failed to claim the job"
            result = checked(client.get(f"/api/v1/jobs/{job['id']}"))
            write(output / "job.json", result)
            if result["status"] != "SUCCEEDED":
                raise RuntimeError(result)
            assert checked(client.get(root+"/review")) == approved
            assert client.get(root+f"/motion/jobs/{job['id']}/video").status_code == 200
            with SessionLocal() as db:
                project = db.get(Project, project_id)
                assert (project.edl, project.plan, project.script) == original
                row = db.get(Job, job["id"])
                write(output / "derived-plan.json", row.payload)
            write(output / "proof.json", {
                "project_id": project_id, "job_id": job["id"], "variant": variant,
                "storyboard_sha256": board["sha256"], "approval": approved,
                "result": result["result"], "original_project_unchanged": True,
                "human_visual_and_listening_approval": "PENDING",
            })
            filename = f"mediagrid-{name}-{variant.replace('_', '-')}.mp4"
            shutil.copy2(result["result"]["output"], output / filename)
            print(json.dumps({"variant": variant, "folder": str(output),
                              "sha256": result["result"]["sha256"],
                              "render_seconds": result["result"]["render_seconds"]}), flush=True)
    assert hashlib.sha256(source_db.read_bytes()).hexdigest() == original_hash
    write(folder / "isolation.json", {"source_db_sha256_unchanged": original_hash,
          "source": str(source), "copied_with": "sqlite3 backup, mode=ro",
          "storyboard_sha256": board["sha256"],
          "approved_snapshot_sha256": approved["current_snapshot_sha256"],
          "new_storyboard_decisions": 0, "schema_changes": 0})


if __name__ == "__main__":
    main()

