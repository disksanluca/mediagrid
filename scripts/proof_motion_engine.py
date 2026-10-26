"""End-to-end M4 proof in a NEW disposable directory, using API and leased worker."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_motion_recipes import PRODUCTIONS  # noqa: E402
from scripts.motion_engine_media import create_media  # noqa: E402
from scripts.proof_creative_motion import checked  # noqa: E402


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def seed_project(client, label, files, recipe_version="1.1.0"):
    from scripts.motion_recipes_v12 import PRODUCTIONS_V12

    p = (PRODUCTIONS_V12 if recipe_version == "1.2.0" else PRODUCTIONS)[label]
    channel = checked(
        client.post(
            "/api/v1/channels",
            json={
                "name": f"M4 {label}",
                "slug": f"m4-{label}",
                "niche": "Original fictional proof",
                "default_engine": {"sports": "football", "music": "music", "geo": "geo"}[label],
            },
        )
    )
    project = checked(
        client.post(
            "/api/v1/projects",
            json={
                "channel_id": channel["id"],
                "title": f"M4 {label} — original",
                "topic": "Original fictional audiovisual study",
                "format": p["format"],
            },
        )
    )
    assets = {}
    for slot, (path, mime) in files.items():
        with path.open("rb") as source:
            assets[slot] = checked(
                client.post(
                    "/api/v1/assets",
                    files={"file": (path.name, source, mime)},
                    data={
                        "rights_status": "OWNED",
                        "commercial_use": "true",
                        "creator": "MediaGrid original procedural study",
                        "license_name": "CC0-1.0",
                    },
                )
            )["id"]
    root = f"/api/v1/projects/{project['id']}/creative"
    checked(
        client.put(
            f"/api/v1/channels/{channel['id']}/creative-dna",
            json={
                "expected_revision": 0,
                "content": {
                    "palette": p["palette"],
                    "font_display": p.get("fonts", ["Barlow Condensed"] * 2)[0],
                    "font_body": p.get("fonts", ["Barlow Condensed"] * 2)[1],
                    "tone": "Original synthetic audiovisual study",
                    "energy": "balanced",
                },
            },
        )
    )
    checked(
        client.put(
            root + "/brief",
            json={
                "expected_revision": 0,
                "content": {
                    "topic": project["topic"],
                    "audience": "Motion review team",
                    "objective": (
                        "Evaluate shared audiovisual motion primitives with original media"
                    ),
                    "format": p["format"],
                    "duration_ms": sum(p["durations"]),
                    "fps": 30,
                    "factual_mode": "FICTIONAL",
                    "asset_ids": list(assets.values()),
                    "sources": [],
                },
            },
        )
    )
    directions = checked(
        client.post(
            root + "/directions",
            json={"expected_revision": 0, "expected_brief_revision": 1, "expected_dna_revision": 1},
        )
    )
    start, shots = 0, []
    for i, duration in enumerate(p["durations"]):
        shots.append(
            {
                "id": f"shot-{i + 1}",
                "start_ms": start,
                "duration_ms": duration,
                "beat": f"Original {label} act {i + 1}",
                "on_screen_text": p["titles"][i],
                "visual_description": f"Original {label} composition using shared primitives",
                "camera_intent": "Layered parallax",
                "motion_intent": "Intentional keyframes",
                "audio_cue": "Original score with authored transients",
                "asset_ids": list(assets.values()),
                "claim_ids": [],
            }
        )
        start += duration
    checked(
        client.put(
            root + "/storyboard",
            json={
                "expected_revision": 0,
                "expected_direction_revision": 1,
                "content": {
                    "direction_id": directions["content"]["directions"][1]["id"],
                    "duration_ms": start,
                    "fps": 30,
                    "shots": shots,
                },
            },
        )
    )
    state = checked(client.get(root + "/review"))
    checked(
        client.post(
            root + "/decision",
            json={
                "expected_revision": 0,
                "expected_storyboard_revision": 1,
                "expected_snapshot_sha256": state["current_snapshot_sha256"],
                "decision": "APPROVE",
                "actor": "M4 explicitly authorized synthetic fixture operator",
                "notes": (
                    "Synthetic storyboard proof only. Human audiovisual approval remains pending."
                ),
                "storyboard_reviewed": True,
                "rights_checked": True,
                "facts_checked": True,
            },
        )
    )
    recipe = next(
        r
        for r in checked(client.get("/api/v1/creative/motion/recipes"))["recipes"]
        if r["id"] == p["id"] and r["version"] == recipe_version
    )
    request = {
        "expected_storyboard_revision": 1,
        "expected_snapshot_sha256": state["current_snapshot_sha256"],
        "recipe": {k: recipe[k] for k in ("id", "version", "sha256")},
        "asset_bindings": assets,
        "quality": "final",
    }
    return project, root, request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--only", choices=list(PRODUCTIONS))
    parser.add_argument("--concurrency", type=int, choices=(1, 2), default=2)
    parser.add_argument("--recipe-version", choices=("1.1.0", "1.2.0"), default="1.2.0")
    parser.add_argument("--approve-synthetic-storyboards", action="store_true")
    args = parser.parse_args()
    if not args.approve_synthetic_storyboards:
        parser.error("Explicit synthetic fixture approval flag required")
    base = (ROOT / "data/m4-complete-proof").resolve()
    folder = (base / args.run).resolve()
    if folder.exists() or folder == base or not folder.is_relative_to(base):
        parser.error("Use a new child directory under data/m4-complete-proof")
    folder.mkdir(parents=True)
    os.environ.update(
        {
            "DATABASE_URL": "sqlite:///" + (folder / "workspace.db").as_posix(),
            "MEDIAGRID_DATA_DIR": str(folder),
            "MEDIAGRID_MODE": "LOCAL",
            "ALLOW_PAID_AI": "false",
            "MEDIAGRID_RENDERER_ROOT": str(ROOT / "apps/renderer"),
            "MEDIAGRID_NODE_PATH": shutil.which("node") or "",
            "MEDIAGRID_RENDER_CONCURRENCY": str(args.concurrency),
        }
    )
    from fastapi.testclient import TestClient

    from apps.api.config import get_settings
    from apps.api.database import SessionLocal
    from apps.api.main import app
    from apps.api.models import Job, Project
    from workers.render.main import media_one

    reports = []
    with TestClient(app) as client:
        for label in [args.only] if args.only else PRODUCTIONS:
            output = folder / label
            output.mkdir()
            files = create_media(
                output,
                label,
                sum(PRODUCTIONS[label]["durations"]) / 1000,
                get_settings().mediagrid_ffmpeg_path or "ffmpeg",
                version=args.recipe_version,
            )
            project, root, request = seed_project(client, label, files, args.recipe_version)
            preview = checked(client.post(root + "/motion/engine/preview", json=request))
            write(output / "preview.json", preview)
            with SessionLocal() as db:
                row = db.get(Project, project["id"])
                before = (row.edl, row.plan, row.script)
            job = checked(client.post(root + "/motion/engine/render", json=request))
            repeated = checked(client.post(root + "/motion/engine/render", json=request))
            assert job["id"] == repeated["id"]
            started = perf_counter()
            stop_path = output / "measurement.stop"
            sampler = None
            if os.name == "nt":
                sampler = subprocess.Popen(
                    [
                        shutil.which("pwsh") or "powershell",
                        "-NoProfile",
                        "-File",
                        str(ROOT / "scripts/measure-motion-process.ps1"),
                        "-RootProcessId",
                        str(os.getpid()),
                        "-StopPath",
                        str(stop_path),
                        "-OutputPath",
                        str(output / "performance.json"),
                    ],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            for _ in range(20):
                if not media_one():
                    raise RuntimeError("Worker could not claim an outstanding job")
                current = checked(client.get(f"/api/v1/jobs/{job['id']}"))
                if current["status"] in {"SUCCEEDED", "FAILED", "BLOCKED"}:
                    break
            if sampler:
                stop_path.touch()
                sampler.wait(timeout=20)
                stop_path.unlink()
            if current["status"] != "SUCCEEDED":
                write(output / "failed-job.json", current)
                raise RuntimeError(current)
            with SessionLocal() as db:
                row = db.get(Project, project["id"])
                assert before == (row.edl, row.plan, row.script)
                payload = db.get(Job, job["id"]).payload
                assert payload == {"plan": preview["plan"], "plan_sha256": preview["plan_sha256"]}
                write(output / "derived-plan.json", payload)
            assert checked(client.get(root + "/review"))["status"] == "APPROVED_STORYBOARD"
            assert client.get(root + f"/motion/jobs/{job['id']}/video").status_code == 200
            review = checked(
                client.post(
                    root + f"/motion/jobs/{job['id']}/review",
                    json={
                        "expected_revision": 0,
                        "expected_plan_sha256": preview["plan_sha256"],
                        "expected_video_sha256": current["result"]["sha256"],
                        "decision": "REQUEST_REVIEW",
                        "notes": "Real original proof ready for human audiovisual evaluation.",
                    },
                )
            )
            assert review["status"] == "REQUEST_REVIEW"
            report = {
                "label": label,
                "project_id": project["id"],
                "job": current,
                "wall_seconds": round(perf_counter() - started, 3),
                "concurrency": args.concurrency,
                "recipe": request["recipe"],
                "review": review,
                "original_project_unchanged": True,
                "human_artistic_approval": "PENDING",
            }
            write(output / "proof.json", report)
            shutil.copyfile(current["result"]["output"], output / f"{label}-motion.mp4")
            reports.append(report)
            print(
                json.dumps(
                    {
                        "completed": label,
                        "mp4": str(output / f"{label}-motion.mp4"),
                        "seconds": report["wall_seconds"],
                    }
                ),
                flush=True,
            )
    write(folder / "proofs.json", reports)


if __name__ == "__main__":
    main()
