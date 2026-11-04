"""Disposable Ollama -> Creative Director -> Kokoro -> M4 narrative POV proof."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def checked(response):
    if response.status_code >= 400:
        raise RuntimeError(f"{response.status_code}: {response.text}")
    return response.json()


def run(command, *, environment=None, timeout=1800):
    started = time.monotonic()
    result = subprocess.run(
        [str(item) for item in command], check=True, capture_output=True, text=True,
        timeout=timeout, env=environment,
    )
    return result, round((time.monotonic()-started)*1000)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--kokoro-python", required=True, type=Path)
    parser.add_argument("--kokoro-cache", required=True, type=Path)
    parser.add_argument("--approve-synthetic-storyboard", action="store_true")
    args = parser.parse_args()
    if not args.approve_synthetic_storyboard:
        parser.error("Explicit approval of the fictional disposable storyboard is required")
    base = (ROOT / "data/narrative-pov-proof").resolve()
    folder = (base / args.run).resolve()
    if folder.exists() or folder == base or not folder.is_relative_to(base):
        parser.error("Use a new isolated run directory")
    if not args.kokoro_python.is_file() or not args.kokoro_cache.is_dir():
        parser.error("Kokoro runtime/cache is unavailable")
    folder.mkdir(parents=True)
    fixture_path = ROOT / "tests/fixtures/narrative_pov_editorial.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    os.environ.update({
        "DATABASE_URL": "sqlite:///" + (folder / "workspace.db").as_posix(),
        "MEDIAGRID_DATA_DIR": str(folder),
        "MEDIAGRID_MODE": "LOCAL",
        "MEDIAGRID_AGENTS_ENABLED": "true",
        "MEDIAGRID_AGENTS_MODEL": "qwen3:4b-instruct",
        "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
        "MEDIAGRID_TTS_PROVIDER": "kokoro",
        "MEDIAGRID_KOKORO_PYTHON": str(args.kokoro_python.resolve()),
        "MEDIAGRID_KOKORO_MODEL_DIR": str(args.kokoro_cache.resolve()),
        "MEDIAGRID_KOKORO_VOICE": "pm_alex",
        "MEDIAGRID_KOKORO_SPEED": "1.08",
        "MEDIAGRID_KOKORO_OFFLINE": "true",
        "MEDIAGRID_RENDERER_ROOT": str(ROOT / "apps/renderer"),
        "MEDIAGRID_NODE_PATH": shutil.which("node") or "",
        "MEDIAGRID_RENDER_CONCURRENCY": "1",
        "ALLOW_PAID_AI": "false", "DRY_RUN": "true",
    })
    from apps.api.creative.contracts import CreativeStoryboard
    from apps.api.creative.local_agents import ScriptDraft

    editorial_script = ScriptDraft.model_validate(fixture["script"])
    editorial_board = CreativeStoryboard.model_validate(fixture["storyboard"])
    media = folder / "media"
    media.mkdir()
    metrics = {
        "started_at": time.time(), "steps": {},
        "editorial_source": fixture["provenance"],
        "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
    }
    segments = []
    for shot, beat in zip(editorial_board.shots, editorial_script.beats, strict=True):
        segments.append({
            "id": shot.id, "text": beat.narration,
            "start_ms": shot.start_ms + shot.narration_start_ms,
            "slot_ms": shot.duration_ms - shot.narration_start_ms,
        })
    segment_path = media / "narration-segments.json"
    write(segment_path, segments)
    narration = media / "narration.wav"
    timing = media / "narration-timing.json"
    environment = os.environ.copy()
    environment.update({
        "HF_HOME": str(args.kokoro_cache.resolve()), "CUDA_VISIBLE_DEVICES": "",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
    })
    _, tts_ms = run([
        args.kokoro_python, ROOT / "scripts/kokoro_tts.py",
        "--segments-json", segment_path, "--output", narration,
        "--timing-output", timing, "--voice", "pm_alex", "--speed", "1.08",
    ], environment=environment)
    metrics["steps"]["kokoro_tts"] = {"wall_ms": tts_ms, "device": "CPU"}
    mix = media / "narrative-mix.wav"
    mix_report = media / "mix-report.json"
    _, mix_ms = run([
        sys.executable, ROOT / "scripts/build_narrative_mix.py",
        "--narration", narration, "--timings", timing,
        "--output", mix, "--report", mix_report,
    ])
    metrics["steps"]["audio_mix"] = {"wall_ms": mix_ms}

    from fastapi.testclient import TestClient

    from apps.api.config import get_settings
    from apps.api.main import app
    from workers.render.main import media_one

    ffmpeg = str(get_settings().mediagrid_ffmpeg_path or "ffmpeg")
    ffprobe = str(get_settings().mediagrid_ffprobe_path or "ffprobe")
    with TestClient(app) as client:
        with mix.open("rb") as stream:
            mix_asset = checked(client.post(
                "/api/v1/assets",
                files={"file": ("narrative-mix.wav", stream, "audio/wav")},
                data={
                    "rights_status": "OWNED", "commercial_use": "true",
                    "creator": (
                        "MediaGrid original editorial script, Kokoro narration and "
                        "procedural MediaGrid mix"
                    ),
                    "license_name": "Original audio; Kokoro code and weights Apache-2.0",
                },
            ))
        channel = checked(client.post("/api/v1/channels", json={
            "name": "Narrative POV Lab", "slug": "narrative-pov-lab",
            "niche": "Fictional illustrated stories", "default_engine": "clips",
        }))
        project = checked(client.post("/api/v1/projects", json={
            "channel_id": channel["id"],
            "title": "O celular usado que ensinou Caio a negociar",
            "topic": (
                "História fictícia em segunda pessoa: um jovem compra um celular usado, "
                "encontra falhas na tela e na bateria, negocia com calma e aprende a "
                "testar, registrar e combinar as condições antes de pagar."
            ),
            "format": "vertical",
        }))
        root = f"/api/v1/projects/{project['id']}/creative"
        dna = checked(client.put(f"/api/v1/channels/{channel['id']}/creative-dna", json={
            "expected_revision": 0,
            "content": {
                "palette": [
                    "#111827", "#F8FAFC", "#F4B942", "#4FD1C5",
                    "#EF5B5B", "#7C5CFC", "#334155", "#F2C6A0",
                ],
                "font_display": "Barlow Condensed", "font_body": "IBM Plex Sans",
                "tone": "Webtoon íntimo, claro e esperançoso",
                "energy": "balanced",
                "must_have": [
                    "Caio com cabelo preto ondulado e moletom mostarda",
                    "quatro ambientes em camadas", "interfaces de celular",
                    "mudanças legíveis de expressão e pose",
                ],
                "avoid": ["marcas reais", "resultados factuais", "composição repetida"],
                "max_words_per_card": 7,
            },
        }))
        brief = checked(client.put(root + "/brief", json={
            "expected_revision": 0,
            "content": {
                "topic": project["topic"],
                "audience": "Jovens adultos comprando eletrônicos usados",
                "objective": (
                    "Contar uma história ficcional causal que ensine a verificar o "
                    "aparelho, registrar o estado e negociar com calma."
                ),
                "format": "vertical", "duration_ms": 56000, "fps": 30,
                "language": "pt-BR", "factual_mode": "FICTIONAL",
                "asset_ids": [mix_asset["id"]],
                "style_notes": (
                    "Cartoon/webtoon 2D, personagem consistente, cutout limitado, "
                    "parallax, câmera motivada e quatro ambientes distintos."
                ),
                "restrictions": [
                    "Não usar marcas ou aplicativos reais",
                    "Não inventar preço, garantia legal ou estatística",
                    "Cada beat deve caber em até 6,5 segundos de locução",
                ],
            },
        }))

        def generate(task, direction_id=None, *, required=True):
            queued = checked(client.post(root + "/agents/jobs", json={
                "task": task, "expected_brief_revision": 1,
                "expected_dna_revision": 1, "direction_id": direction_id,
            }))
            if not media_one():
                raise RuntimeError(f"Worker did not claim {task}")
            completed = checked(client.get(f"/api/v1/jobs/{queued['id']}"))
            write(folder / "agents" / f"{task}.json", completed)
            if completed["status"] != "SUCCEEDED":
                metrics["steps"][f"agent_{task}"] = {
                    "status": completed["status"], "error": completed["error"],
                }
                if required:
                    raise RuntimeError(f"{task}: {completed['error']}")
                return completed
            metrics["steps"][f"agent_{task}"] = {
                "latency_ms": completed["result"]["latency_ms"],
                "prompt_tokens": completed["result"]["prompt_tokens"],
                "response_tokens": completed["result"]["response_tokens"],
                "repairs": completed["result"]["repair_count"],
                "resources_before": completed["result"]["resources_before"],
                "resources_after": completed["result"]["resources_after"],
            }
            return completed

        script = generate("script", required=False)
        if script["status"] != "SUCCEEDED":
            from apps.api.creative.hashing import content_sha256
            from apps.api.database import SessionLocal
            from apps.api.models import Job, JobStatus

            content = editorial_script.model_dump(mode="json")
            with SessionLocal() as db:
                editorial_job = Job(
                    project_id=project["id"], job_type="CREATIVE_AI",
                    status=JobStatus.SUCCEEDED.value, progress=100,
                    payload={
                        "task": "script", "brief_sha256": brief["sha256"],
                        "dna_sha256": dna["sha256"], "context": {},
                    },
                    result={
                        "task": "script", "provider": "editorial_fixture",
                        "model": None, "prompt_version": "editorial_fixture_v1",
                        "content": content, "content_sha256": content_sha256(content),
                        "brief_sha256": brief["sha256"], "dna_sha256": dna["sha256"],
                        "review_status": "NEEDS_REVIEW", "repair_count": 0,
                        "latency_ms": 0, "prompt_tokens": 0, "response_tokens": 0,
                        "resources_before": {}, "resources_after": {},
                        "origin": fixture["provenance"],
                    },
                )
                db.add(editorial_job)
                db.commit()
                db.refresh(editorial_job)
                editorial_script_job_id = editorial_job.id
            write(folder / "agents" / "script-editorial-input.json", {
                "job_id": editorial_script_job_id, "provider": "editorial_fixture",
                "content": content, "origin": fixture["provenance"],
            })
        else:
            editorial_script_job_id = None
        directions = generate("directions")
        direction_set = checked(client.post(
            root + f"/agents/jobs/{directions['id']}/adopt-directions",
            json={"expected_revision": 0, "expected_brief_revision": 1,
                  "expected_dna_revision": 1},
        ))
        chosen = direction_set["content"]["directions"][0]["id"]
        storyboard_job = generate("storyboard", chosen)
        write(folder / "storyboard-agent.json", storyboard_job["result"]["content"])
        if script["status"] == "SUCCEEDED":
            write(folder / "script-agent.json", script["result"]["content"])

        board = fixture["storyboard"]
        board["direction_id"] = chosen
        for shot in board["shots"]:
            shot["asset_ids"] = [mix_asset["id"]]
        storyboard = checked(client.put(root + "/storyboard", json={
            "expected_revision": 0,
            "expected_direction_revision": direction_set["revision"],
            "content": board,
        }))
        write(folder / "script-used.json", fixture["script"])
        write(folder / "agent-editorial-disposition.json", {
            "agent_script_job_id": script["id"],
            "editorial_script_job_id": editorial_script_job_id,
            "agent_storyboard_job_id": storyboard_job["id"],
            "adopted": False,
            "reason": (
                "The final isolated proof uses the original editorial fixture; local "
                "agent drafts remain NEEDS_REVIEW and cannot approve themselves."
            ),
        })
        review = checked(client.get(root + "/review"))
        if review["blockers"]:
            raise RuntimeError(f"Storyboard blockers: {review['blockers']}")
        checked(client.post(root + "/decision", json={
            "expected_revision": 0,
            "expected_storyboard_revision": storyboard["revision"],
            "expected_snapshot_sha256": review["current_snapshot_sha256"],
            "decision": "APPROVE", "actor": "Disposable narrative proof fixture",
            "notes": (
                "Fictional isolated technical proof; audiovisual publication remains disabled."
            ),
            "storyboard_reviewed": True, "rights_checked": True, "facts_checked": True,
        }))
        final_board = checked(client.get(root + "/storyboard"))
        write(folder / "storyboard-used.json", final_board)
        continuity = generate("continuity")
        references = generate("references")
        motion = generate("motion")
        qa = generate("qa")
        if motion["result"]["content"]["recipe_id"] != "pov.webtoon-cutout":
            raise RuntimeError("Motion planner did not choose the compatible narrative recipe")

        recipes = checked(client.get("/api/v1/creative/motion/recipes"))["recipes"]
        recipe = next(
            item for item in recipes
            if item["id"] == "pov.webtoon-cutout" and item["version"] == "1.3.0"
        )
        request = {
            "expected_storyboard_revision": storyboard["revision"],
            "expected_snapshot_sha256": review["current_snapshot_sha256"],
            "recipe": {field: recipe[field] for field in ("id", "version", "sha256")},
            "asset_bindings": {"mix": mix_asset["id"]},
            "quality": "final",
        }
        preview = checked(client.post(root + "/motion/engine/preview", json=request))
        write(folder / "preview.json", preview)
        started = time.monotonic()
        render_job = checked(client.post(root + "/motion/engine/render", json=request))
        if not media_one():
            raise RuntimeError("M4 worker did not claim narrative render")
        rendered = checked(client.get(f"/api/v1/jobs/{render_job['id']}"))
        metrics["steps"]["m4_render"] = {
            "wall_ms": round((time.monotonic()-started)*1000),
            "job_id": render_job["id"],
        }
        write(folder / "render-job.json", rendered)
        if rendered["status"] != "SUCCEEDED":
            raise RuntimeError(rendered["error"])
        video = media / "narrative-pov-studio.mp4"
        shutil.copyfile(rendered["result"]["output"], video)
        artifact = checked(client.post(
            root + f"/motion/jobs/{rendered['id']}/review",
            json={
                "expected_revision": 0,
                "expected_plan_sha256": preview["plan_sha256"],
                "expected_video_sha256": rendered["result"]["sha256"],
                "decision": "REQUEST_REVIEW",
                "notes": (
                    "Illustrated cutout POV with local narration; human visual and "
                    "listening review remains required."
                ),
            },
        ))
        write(folder / "artifact-review.json", artifact)

    probe_result, _ = run([
        ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", video,
    ])
    (media / "ffprobe.json").write_text(probe_result.stdout, encoding="utf-8")
    run([ffmpeg, "-v", "error", "-i", video, "-f", "null", "NUL"])
    frames = media / "frames"
    frames.mkdir()
    for index in range(8):
        run([
            ffmpeg, "-v", "error", "-ss", str(index*7+3.5), "-i", video,
            "-frames:v", "1", "-y", frames / f"scene-{index+1:02d}.png",
        ])
    run([
        ffmpeg, "-v", "error", "-i", video, "-vf",
        "fps=1/7,scale=270:480,tile=4x2", "-frames:v", "1", "-y",
        media / "contact-sheet.png",
    ])
    metrics.update({
        "finished_at": time.time(),
        "video_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
        "narration_sha256": hashlib.sha256(narration.read_bytes()).hexdigest(),
        "mix_sha256": hashlib.sha256(mix.read_bytes()).hexdigest(),
        "storyboard_sha256": hashlib.sha256(
            (folder / "storyboard-used.json").read_bytes()
        ).hexdigest(),
        "artifact_status": "REQUEST_REVIEW",
        "publication_enabled": False,
        "agent_job_ids": {
            "script": script["id"], "directions": directions["id"],
            "storyboard": storyboard_job["id"], "continuity": continuity["id"],
            "references": references["id"], "motion": motion["id"], "qa": qa["id"],
        },
    })
    write(folder / "proof.json", metrics)
    print(json.dumps({
        "video": str(video), "sha256": metrics["video_sha256"],
        "contact_sheet": str(media / "contact-sheet.png"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
