"""Recheck the motion agent against an existing disposable local proof only."""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    base = (ROOT / "data/local-agent-proof").resolve()
    folder = (base / args.run).resolve()
    if folder == base or not folder.is_relative_to(base) or not (folder / "proof.json").is_file():
        parser.error("An existing disposable local-agent proof is required")
    os.environ.update({
        "DATABASE_URL": "sqlite:///" + (folder / "workspace.db").as_posix(),
        "MEDIAGRID_DATA_DIR": str(folder), "MEDIAGRID_MODE": "LOCAL",
        "MEDIAGRID_AGENTS_ENABLED": "true",
        "MEDIAGRID_AGENTS_MODEL": "qwen3:4b-instruct",
        "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
        "ALLOW_PAID_AI": "false", "DRY_RUN": "true",
    })
    from fastapi.testclient import TestClient

    from apps.api.main import app
    from workers.render.main import media_one

    proof = json.loads((folder / "proof.json").read_text(encoding="utf-8"))
    root = f"/api/v1/projects/{proof['pov_project_id']}/creative"
    with TestClient(app) as client:
        queued = client.post(root + "/agents/jobs", json={
            "task": "motion", "expected_brief_revision": 1,
            "expected_dna_revision": 1,
        })
        queued.raise_for_status()
        if not media_one():
            raise RuntimeError("Worker did not claim motion planning")
        done = client.get(f"/api/v1/jobs/{queued.json()['id']}")
        done.raise_for_status()
        value = done.json()
        (folder / "motion-replan-job.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        if value["status"] != "SUCCEEDED":
            raise RuntimeError(f"Motion planning failed: {value['error']}")
        print(json.dumps({"recipe": value["result"]["content"]["recipe_id"],
                          "readiness": value["result"]["motion_readiness"],
                          "repair_count": value["result"]["repair_count"]}))


if __name__ == "__main__":
    main()
