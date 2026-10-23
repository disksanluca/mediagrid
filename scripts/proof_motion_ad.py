"""Render a fictional ad in an isolated local database for technical review.

Run from the repository root with the development renderer and FFmpeg installed.
This proof never approves or exports the synthetic advertisement.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
data = root / "data" / "motion-ad-proof"
data.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{(data / 'mediagrid.db').as_posix()}"
os.environ["MEDIAGRID_DATA_DIR"] = str(data)
os.environ["MEDIAGRID_RENDERER_ROOT"] = str(root / "apps" / "renderer")
node = shutil.which("node")
if not node:
    raise SystemExit("Node.js local indisponível")
os.environ["MEDIAGRID_NODE_PATH"] = node

from fastapi.testclient import TestClient  # noqa: E402

from apps.api.main import app  # noqa: E402
from workers.render.main import media_one, render_one  # noqa: E402


def ok(response):
    if response.status_code >= 400:
        raise RuntimeError(f"API {response.status_code}: {response.text}")
    return response.json()


with TestClient(app) as client:
    channel = ok(client.post("/api/v1/channels", json={
        "name": "Prova sintética de anúncios",
        "slug": f"prova-motion-ad-{uuid4().hex[:8]}",
        "niche": "Teste técnico", "default_engine": "clips",
    }))
    project = ok(client.post("/api/v1/motion-ads/projects", json={
        "channel_id": channel["id"], "format": "vertical",
        "product_name": "Bloco Fictício", "audience": "pessoas que criam vídeos",
        "hook": "Uma ideia pode começar no papel.",
        "problem": "Seus rascunhos estão em vários lugares.",
        "benefit": "Coloque cada rascunho em uma só tela.",
        "call_to_action": "Veja o Bloco Fictício.",
        "brand_color": "#c4d4ef",
    }))
    project_id = project["id"]
    voice = ok(client.post(f"/api/v1/projects/{project_id}/voice"))
    if not media_one():
        raise RuntimeError("Worker não recebeu job de voz")
    voice_state = ok(client.get(f"/api/v1/jobs/{voice['job_id']}"))
    if voice_state["status"] != "SUCCEEDED":
        raise RuntimeError(f"Voz falhou: {voice_state['error']}")
    render = ok(client.post(f"/api/v1/projects/{project_id}/render"))
    if not render_one():
        raise RuntimeError("Worker não recebeu job de render")
    render_state = ok(client.get(f"/api/v1/jobs/{render['job_id']}"))
    if render_state["status"] != "SUCCEEDED":
        raise RuntimeError(f"Render falhou: {render_state['error']}")
    project_state = ok(client.get(f"/api/v1/projects/{project_id}"))
    if project_state["status"] != "QC":
        raise RuntimeError(f"Status inesperado: {project_state['status']}")
    if client.get(f"/api/v1/projects/{project_id}/export").status_code != 409:
        raise RuntimeError("Exportação sintética sem revisão deveria ser bloqueada")

video = data / "renders" / f"{project_id}.mp4"
probe = subprocess.run([
    "ffprobe", "-v", "error", "-show_entries",
    "format=duration:stream=codec_name,codec_type,width,height",
    "-of", "json", str(video),
], check=True, capture_output=True, text=True)
metadata = json.loads(probe.stdout)
streams = metadata["streams"]
picture = next(stream for stream in streams if stream["codec_type"] == "video")
audio = next(stream for stream in streams if stream["codec_type"] == "audio")
if (picture["width"], picture["height"]) != (1080, 1920):
    raise RuntimeError("Dimensões incorretas")
report = {
    "project_id": project_id, "job_id": render["job_id"],
    "status": "QC", "export": "BLOCKED_REVIEW",
    "duration_seconds": metadata["format"]["duration"],
    "video": picture["codec_name"], "audio": audio["codec_name"],
    "dimensions": [picture["width"], picture["height"]],
    "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
    "path": str(video),
}
(data / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
