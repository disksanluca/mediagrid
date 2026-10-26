"""Reproduce M3 only in a new disposable directory under data/creative-m3-proof."""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.m3_score import create_score  # noqa: E402

DNA = {
    "palette": ["#0B1013", "#F4F0E6", "#D7FF3F"],
    "font_display": "Barlow Condensed",
    "font_body": "Barlow Condensed",
    "tone": "Esporte ficcional, gráfico e enérgico",
    "energy": "intense",
    "must_have": ["Tipografia legível", "Áudio original sincronizado"],
    "avoid": ["Resultados reais", "Marcas de clubes", "Imagens de terceiros"],
}
SHOTS = [
    {
        "id": "impact",
        "start_ms": 0,
        "duration_ms": 2000,
        "beat": "Abertura impactante",
        "on_screen_text": "ENTRE\nEM JOGO",
        "visual_description": "Tipografia sobre órbitas e faixa diagonal",
        "camera_intent": "Aproximação leve",
        "motion_intent": "Máscara, escala e easing",
        "audio_cue": "Impacto original em 0 s e pulso a 120 BPM",
    },
    {
        "id": "reveal",
        "start_ms": 2000,
        "duration_ms": 3000,
        "beat": "Revelação visual",
        "on_screen_text": "SINTA\nO CAMPO",
        "visual_description": "Bola original vetorial em órbita",
        "camera_intent": "Aproximação e parallax",
        "motion_intent": "Rotação contínua, revelação e drift",
        "audio_cue": "Impacto em 2 s, arpejo original",
    },
    {
        "id": "play",
        "start_ms": 5000,
        "duration_ms": 4000,
        "beat": "Composição esportiva dinâmica",
        "on_screen_text": "MUDE\nO JOGO",
        "visual_description": "Campo conceitual com três posições e rota",
        "camera_intent": "Rotação e zoom controlados",
        "motion_intent": "Rota progressiva e transição diagonal",
        "audio_cue": "Impacto em 5 s e subdivisão percussiva",
    },
    {
        "id": "resolve",
        "start_ms": 9000,
        "duration_ms": 3000,
        "beat": "Clímax e encerramento",
        "on_screen_text": "É AGORA.",
        "visual_description": "Tipografia central e círculo expansivo",
        "camera_intent": "Estabilização com drift",
        "motion_intent": "Expansão e assentamento",
        "audio_cue": "Impacto em 9 s e cauda harmônica até 12 s",
    },
]


def checked(response):
    if response.is_error:
        raise RuntimeError(f"{response.status_code}: {response.text}")
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="final")
    parser.add_argument("--quality", choices=["preview", "final"], default="final")
    parser.add_argument("--approve-synthetic-storyboard", action="store_true")
    args = parser.parse_args()
    if not args.approve_synthetic_storyboard:
        parser.error(
            "Explicit --approve-synthetic-storyboard is required for the requested fixture"
        )
    base = (ROOT / "data" / "creative-m3-proof").resolve()
    folder = (base / args.run).resolve()
    if not folder.is_relative_to(base) or folder == base or folder.exists():
        parser.error("Use a new child directory within data/creative-m3-proof")
    folder.mkdir(parents=True)
    os.environ.update(
        {
            "DATABASE_URL": "sqlite:///" + (folder / "workspace.db").as_posix(),
            "MEDIAGRID_DATA_DIR": str(folder),
            "MEDIAGRID_MODE": "LOCAL",
            "ALLOW_PAID_AI": "false",
            "MEDIAGRID_RENDERER_ROOT": str(ROOT / "apps/renderer"),
            "MEDIAGRID_NODE_PATH": shutil.which("node") or "",
            "MEDIAGRID_RENDER_CONCURRENCY": "2",
        }
    )
    # Never import database/config before isolating paths above.
    from fastapi.testclient import TestClient

    from apps.api.database import SessionLocal
    from apps.api.main import app
    from apps.api.models import Job, Project
    from workers.render.main import media_one

    score = folder / "original-score.wav"
    score_info = create_score(score)
    (folder / "score-manifest.json").write_text(json.dumps(score_info, indent=2), encoding="utf-8")
    with TestClient(app) as client:
        channel = checked(
            client.post(
                "/api/v1/channels",
                json={
                    "name": "M3 Motion Lab",
                    "slug": "m3-motion-lab",
                    "niche": "Esporte ficcional",
                    "default_engine": "football",
                },
            )
        )
        project = checked(
            client.post(
                "/api/v1/projects",
                json={
                    "channel_id": channel["id"],
                    "title": "Entre em jogo — estudo original",
                    "topic": "Manifesto esportivo ficcional em quatro planos",
                    "format": "vertical",
                },
            )
        )
        with score.open("rb") as source:
            asset = checked(
                client.post(
                    "/api/v1/assets",
                    files={"file": ("original-score.wav", source, "audio/wav")},
                    data={
                        "rights_status": "OWNED",
                        "commercial_use": "true",
                        "creator": "MediaGrid M3 procedural score",
                        "license_name": score_info["license"],
                    },
                )
            )
        root = f"/api/v1/projects/{project['id']}/creative"
        checked(
            client.put(
                f"/api/v1/channels/{channel['id']}/creative-dna",
                json={"expected_revision": 0, "content": DNA},
            )
        )
        checked(
            client.put(
                root + "/brief",
                json={
                    "expected_revision": 0,
                    "content": {
                        "topic": project["topic"],
                        "audience": "Público de esportes",
                        "objective": "Testar tipografia, ritmo, composição e sincronização de som",
                        "format": "vertical",
                        "duration_ms": 12000,
                        "fps": 30,
                        "factual_mode": "FICTIONAL",
                        "asset_ids": [asset["id"]],
                        "sources": [],
                    },
                },
            )
        )
        directions = checked(
            client.post(
                root + "/directions",
                json={
                    "expected_revision": 0,
                    "expected_brief_revision": 1,
                    "expected_dna_revision": 1,
                },
            )
        )
        board = checked(
            client.put(
                root + "/storyboard",
                json={
                    "expected_revision": 0,
                    "expected_direction_revision": 1,
                    "content": {
                        "direction_id": directions["content"]["directions"][1]["id"],
                        "duration_ms": 12000,
                        "fps": 30,
                        "shots": [dict(s, asset_ids=[asset["id"]]) for s in SHOTS],
                    },
                },
            )
        )
        state = checked(client.get(root + "/review"))
        approved = checked(
            client.post(
                root + "/decision",
                json={
                    "expected_revision": 0,
                    "expected_storyboard_revision": 1,
                    "expected_snapshot_sha256": state["current_snapshot_sha256"],
                    "decision": "APPROVE",
                    "actor": "M3 fixture operator",
                    "notes": "Explicit synthetic fixture approval for the requested "
                    "0/2/5/9/12s sequence. "
                    "No human audiovisual quality approval is asserted.",
                    "storyboard_reviewed": True,
                    "rights_checked": True,
                    "facts_checked": True,
                },
            )
        )
        request = {
            "expected_storyboard_revision": 1,
            "soundtrack_asset_id": asset["id"],
            "expected_snapshot_sha256": approved["current_snapshot_sha256"],
            "quality": args.quality,
        }
        preview = checked(client.post(root + "/motion/preview", json=request))
        (folder / "preview.json").write_text(
            json.dumps(preview, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        job = checked(client.post(root + "/motion/render", json=request))
        repeated = checked(client.post(root + "/motion/render", json=request))
        assert repeated["id"] == job["id"], "Queue was not idempotent"
        with SessionLocal() as db:
            before = db.get(Project, project["id"])
            original = (before.edl, before.plan, before.script)
        if not media_one():
            raise RuntimeError("Worker did not claim the proof job")
        result = checked(client.get(f"/api/v1/jobs/{job['id']}"))
        (folder / "job.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        if result["status"] != "SUCCEEDED":
            raise RuntimeError(result)
        assert checked(client.get(root + "/review"))["status"] == "APPROVED_STORYBOARD"
        assert client.get(root + f"/motion/jobs/{job['id']}/video").status_code == 200
        with SessionLocal() as db:
            after = db.get(Project, project["id"])
            assert (after.edl, after.plan, after.script) == original
            row = db.get(Job, job["id"])
            (folder / "derived-plan.json").write_text(
                json.dumps(row.payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        (folder / "proof.json").write_text(
            json.dumps(
                {
                    "project_id": project["id"],
                    "channel_id": channel["id"],
                    "job_id": job["id"],
                    "storyboard_sha256": board["sha256"],
                    "result": result["result"],
                    "approval": approved,
                    "original_project_unchanged": True,
                    "artistic_human_review": "PENDING",
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {"folder": str(folder), "job": job["id"], "result": result["result"]},
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
