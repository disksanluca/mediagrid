"""Disposable real Ollama -> Creative Director -> M4 teaser proof."""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.motion_engine_media import create_media  # noqa: E402
from scripts.proof_motion_engine import seed_project  # noqa: E402


def write(path, content):
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--full-pov", action="store_true",
                        help="Render six approved AI shots through the M4 POV recipe")
    parser.add_argument("--approve-synthetic-storyboards", action="store_true")
    args = parser.parse_args()
    if not args.approve_synthetic_storyboards:
        parser.error("Explicit synthetic fixture approval flag required")
    base = (ROOT / "data/local-agent-proof").resolve()
    folder = (base / args.run).resolve()
    if folder.exists() or folder == base or not folder.is_relative_to(base):
        parser.error("Use a new isolated child under data/local-agent-proof")
    folder.mkdir(parents=True)
    os.environ.update({
        "DATABASE_URL": "sqlite:///" + (folder / "workspace.db").as_posix(),
        "MEDIAGRID_DATA_DIR": str(folder), "MEDIAGRID_MODE": "LOCAL",
        "MEDIAGRID_AGENTS_ENABLED": "true",
        "MEDIAGRID_AGENTS_MODEL": "qwen3:4b-instruct",
        "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
        "ALLOW_PAID_AI": "false", "DRY_RUN": "true",
        "MEDIAGRID_RENDERER_ROOT": str(ROOT / "apps/renderer"),
        "MEDIAGRID_NODE_PATH": shutil.which("node") or "",
        "MEDIAGRID_RENDER_CONCURRENCY": "2",
    })
    from fastapi.testclient import TestClient

    from apps.api.config import get_settings
    from apps.api.main import app
    from scripts.proof_creative_motion import checked
    from workers.render.main import media_one

    source = json.loads((ROOT / "tests/fixtures/local-agent-pov-brief.json").read_text(
        encoding="utf-8"))
    with TestClient(app) as client:
        channel = checked(client.post("/api/v1/channels", json={
            "name": "POV original", "slug": "pov-original",
            "niche": "Fictional personal story", "default_engine": "geo",
        }))
        project = checked(client.post("/api/v1/projects", json={
            "channel_id": channel["id"], "title": source["title"],
            "topic": source["narrative"], "format": "vertical",
        }))
        root = f"/api/v1/projects/{project['id']}/creative"
        score_id = None
        if args.full_pov:
            media_dir = folder / "motion"
            media_dir.mkdir()
            files = create_media(media_dir, "geo", 30.0,
                                 get_settings().mediagrid_ffmpeg_path or "ffmpeg",
                                 version="1.2.0")
            score_path, score_mime = files["score"]
            with score_path.open("rb") as stream:
                score_id = checked(client.post("/api/v1/assets",
                    files={"file": (score_path.name, stream, score_mime)},
                    data={"rights_status": "OWNED", "commercial_use": "true",
                          "creator": "MediaGrid original procedural study",
                          "license_name": "CC0-1.0"}))["id"]
        checked(client.put(f"/api/v1/channels/{channel['id']}/creative-dna", json={
            "expected_revision": 0,
            "content": {"palette": ["#101A26", "#F2E7D6", "#7CC4C2"],
                        "font_display": "IBM Plex Sans", "font_body": "IBM Plex Sans",
                        "tone": "Fictional second-person journey", "energy": "balanced"},
        }))
        checked(client.put(root + "/brief", json={
            "expected_revision": 0,
            "content": {"topic": source["narrative"],
                        "audience": "Adults curious about a fictional first sale",
                        "objective": "Create an original second-person fictional POV story",
                        "format": "vertical",
                        "duration_ms": 30000 if args.full_pov else 45000,
                        "fps": 30, "asset_ids": [score_id] if score_id else [],
                        "factual_mode": "FICTIONAL", "style_notes": source["visual_style"],
                        "restrictions": ["Do not name real brands or apps",
                                         "Do not invent specific prices or dates"]},
        }))

        def generate(task, direction_id=None):
            job = checked(client.post(root + "/agents/jobs", json={
                "task": task, "expected_brief_revision": 1,
                "expected_dna_revision": 1, "direction_id": direction_id,
            }))
            if not media_one():
                raise RuntimeError(f"Worker did not claim {task}")
            done = checked(client.get(f"/api/v1/jobs/{job['id']}"))
            write(folder / f"{task}-job.json", done)
            if done["status"] != "SUCCEEDED":
                raise RuntimeError(f"{task}: {done['status']} {done['error']}")
            print(json.dumps({"task": task, "latency_ms": done["result"]["latency_ms"],
                              "tokens": done["result"]["response_tokens"]}), flush=True)
            return done

        script = generate("script")
        directions = generate("directions")
        adopted = checked(client.post(root + f"/agents/jobs/{directions['id']}/adopt-directions",
                                      json={"expected_revision": 0,
                                            "expected_brief_revision": 1,
                                            "expected_dna_revision": 1}))
        chosen = adopted["content"]["directions"][0]["id"]
        board = generate("storyboard", chosen)
        adopted_board = checked(client.post(
            root + f"/agents/jobs/{board['id']}/adopt-storyboard",
            json={"expected_revision": 0, "expected_brief_revision": 1,
                  "expected_dna_revision": 1, "expected_direction_revision": 1},
        ))
        if args.full_pov:
            board_content = adopted_board["content"]
            for shot in board_content["shots"]:
                shot["asset_ids"] = [score_id]
            adopted_board = checked(client.put(root + "/storyboard", json={
                "expected_revision": 1, "expected_direction_revision": 1,
                "content": board_content,
            }))
        review = checked(client.get(root + "/review"))
        if review["blockers"]:
            raise RuntimeError(f"Storyboard blocked: {review['blockers']}")
        checked(client.post(root + "/decision", json={
            "expected_revision": 0,
            "expected_storyboard_revision": adopted_board["revision"],
            "expected_snapshot_sha256": review["current_snapshot_sha256"],
            "decision": "APPROVE", "actor": "Synthetic fixture reviewer",
            "notes": "Fictional test only; no audiovisual publication approval.",
            "storyboard_reviewed": True, "rights_checked": True, "facts_checked": True,
        }))
        write(folder / "pov-storyboard.json", board["result"]["content"])
        continuity = generate("continuity")
        references = generate("references")
        motion = generate("motion")
        qa = generate("qa")

        if args.full_pov:
            recipe = next(item for item in checked(
                client.get("/api/v1/creative/motion/recipes"))["recipes"]
                if item["id"] == "pov.first-sale" and item["version"] == "1.2.0")
            request = {"expected_storyboard_revision": adopted_board["revision"],
                       "expected_snapshot_sha256": review["current_snapshot_sha256"],
                       "recipe": {key: recipe[key] for key in ("id", "version", "sha256")},
                       "asset_bindings": {"score": score_id}, "quality": "final"}
            preview = checked(client.post(root + "/motion/engine/preview", json=request))
            write(media_dir / "preview.json", preview)
            job = checked(client.post(root + "/motion/engine/render", json=request))
            if not media_one():
                raise RuntimeError("M4 worker did not claim the six-shot render")
            done = checked(client.get(f"/api/v1/jobs/{job['id']}"))
            write(media_dir / "render-job.json", done)
            if done["status"] != "SUCCEEDED":
                raise RuntimeError(f"M4 six-shot render failed: {done['error']}")
            target = media_dir / "pov-six-scene.mp4"
            shutil.copyfile(done["result"]["output"], target)
            artifact_review = checked(client.post(
                root + f"/motion/jobs/{done['id']}/review",
                json={"expected_revision": 0,
                      "expected_plan_sha256": preview["plan_sha256"],
                      "expected_video_sha256": done["result"]["sha256"],
                      "decision": "REQUEST_REVIEW",
                      "notes": "Original six-shot POV motion; human artistic review pending."},
            ))
            write(media_dir / "artifact-review.json", artifact_review)
            write(folder / "proof.json", {
                "pov_project_id": project["id"], "script_job_id": script["id"],
                "directions_job_id": directions["id"], "storyboard_job_id": board["id"],
                "continuity_job_id": continuity["id"],
                "references_job_id": references["id"],
                "motion_planning_job_id": motion["id"], "qa_job_id": qa["id"],
                "approved_storyboard_revision": adopted_board["revision"],
                "motion_job_id": done["id"],
                "video_sha256": done["result"]["sha256"],
                "artifact_review": artifact_review["status"],
                "cartoon_illustration": "BLOCKED_NO_ILLUSTRATIONS"})
            print(json.dumps({"mp4": str(target),
                              "sha256": done["result"]["sha256"]}), flush=True)
            return

        # M4 v1 recipes have 2–4 scenes. This is a declared 3-shot teaser derived
        # from the approved six-shot POV, never a claim of full illustrated POV.
        beats = script["result"]["content"]["beats"]
        source_beats = []
        for beat, place in zip((beats[0], beats[1], beats[4]),
                               ("QUARTO", "CAFETERIA", "MESA"), strict=True):
            source_beats.append({
                "beat": beat["narration"][:240],
                "on_screen_text": place + "\n" + " ".join(
                    beat["narration"].split()[:3]).upper()[:28],
                "visual_description": beat["visual"][:800],
            })
        output = folder / "geo"
        output.mkdir()
        files = create_media(output, "geo", 15.0,
                             get_settings().mediagrid_ffmpeg_path or "ffmpeg",
                             version="1.2.0")
        teaser, teaser_root, request = seed_project(
            client, "geo", files, "1.2.0", source_beats=source_beats,
            topic_override=source["narrative"][:500],
        )
        preview = checked(client.post(teaser_root + "/motion/engine/preview", json=request))
        write(output / "preview.json", preview)
        job = checked(client.post(teaser_root + "/motion/engine/render", json=request))
        if not media_one():
            raise RuntimeError("M4 worker did not claim the teaser")
        done = checked(client.get(f"/api/v1/jobs/{job['id']}"))
        write(output / "render-job.json", done)
        if done["status"] != "SUCCEEDED":
            raise RuntimeError(f"M4 teaser failed: {done['error']}")
        shutil.copyfile(done["result"]["output"], output / "pov-teaser-motion.mp4")
        artifact_review = checked(client.post(
            teaser_root + f"/motion/jobs/{done['id']}/review",
            json={"expected_revision": 0,
                  "expected_plan_sha256": preview["plan_sha256"],
                  "expected_video_sha256": done["result"]["sha256"],
                  "decision": "REQUEST_REVIEW",
                  "notes": "Geo M4 teaser from three POV beats; artistic review pending."},
        ))
        write(output / "artifact-review.json", artifact_review)
        write(folder / "proof.json", {"pov_project_id": project["id"],
              "teaser_project_id": teaser["id"], "script_job_id": script["id"],
              "directions_job_id": directions["id"], "storyboard_job_id": board["id"],
              "continuity_job_id": continuity["id"],
              "references_job_id": references["id"],
              "motion_job_id": motion["id"], "qa_job_id": qa["id"],
              "storyboard_review": "APPROVED_SYNTHETIC_FIXTURE",
              "teaser_motion_job_id": done["id"],
              "teaser_sha256": done["result"]["sha256"],
              "teaser_review": artifact_review["status"],
              "full_cartoon_pov": "BLOCKED_NO_ILLUSTRATIONS"})
        print(json.dumps({"mp4": str(output / "pov-teaser-motion.mp4"),
                          "sha256": done["result"]["sha256"]}), flush=True)


if __name__ == "__main__":
    main()
