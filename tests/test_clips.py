"""Speech-window suggestions require human selection and produce real MP4 cuts."""

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.captions import Word
from apps.api.clip_suggestions import suggest_clips
from workers.render.main import media_one


def test_explainable_windows_keep_sentence_bounds_and_diversity() -> None:
    words = [Word(start_ms=index * 1000, end_ms=index * 1000 + 900,
                  text="frase." if index in {9, 19, 29} else "palavra")
             for index in range(30)]
    candidates = suggest_clips(words, 32_000, min_ms=12_000,
                               target_ms=30_000, max_ms=32_000)
    assert len(candidates) >= 2
    assert [(item.start_ms, item.end_ms) for item in candidates[:2]] == [
        (0, 29_900), (10_000, 29_900),
    ]
    assert all(item.context_start_ms <= item.start_ms
               and item.context_end_ms >= item.end_ms for item in candidates)
    assert all("HIGH_SPEECH_COVERAGE" in item.reason_codes for item in candidates)


def synthetic_long_video(path: Path) -> Path:
    subprocess.run([
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-f", "lavfi", "-i", "color=c=blue:s=1280x720:r=15:d=32",
        "-f", "lavfi", "-i", "sine=frequency=330:duration=32",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
        "-shortest", str(path),
    ], check=True, timeout=120)
    return path


def test_clip_analysis_selection_and_two_real_exports(
    client: TestClient, tmp_path: Path
) -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg/FFprobe unavailable before CI installs the desktop runtime")
    source = synthetic_long_video(tmp_path / "long.mp4")
    with source.open("rb") as media:
        response = client.post("/api/v1/assets", files={
            "file": ("long.mp4", media, "video/mp4"),
        }, data={"rights_status": "OWNED", "creator": "synthetic test"})
    assert response.status_code == 201, response.text
    asset_id = response.json()["id"]
    transcript_url = f"/api/v1/assets/{asset_id}/transcript-v2"
    words = [{"start_ms": index * 1000, "end_ms": index * 1000 + 900,
              "text": "frase." if index in {9, 19, 29} else "palavra"}
             for index in range(30)]
    cues = [{"start_ms": start, "end_ms": start + 9900,
             "text": f"Frase sintética {start // 10000 + 1}."}
            for start in (0, 10_000, 20_000)]
    saved = client.put(transcript_url, json={
        "expected_revision": 0, "language": "pt", "words": words, "cues": cues,
    })
    assert saved.status_code == 200, saved.text
    approved = client.post(f"/api/v1/assets/{asset_id}/captions/approve", json={
        "expected_revision": 1,
    })
    assert approved.status_code == 200
    analyze = client.post(f"/api/v1/assets/{asset_id}/clips/analyze")
    assert analyze.status_code == 202, analyze.text
    assert media_one()
    analysis_job = client.get(f"/api/v1/jobs/{analyze.json()['job_id']}").json()
    assert analysis_job["status"] == "SUCCEEDED", analysis_job["error"]
    candidates = client.get(f"/api/v1/assets/{asset_id}/clips").json()
    assert len(candidates) >= 2
    assert candidates[0]["spoken_text"] and candidates[1]["context_before"]
    outputs = []
    first_download = None
    for candidate in candidates[:2]:
        url = f"/api/v1/assets/{asset_id}/clips/{candidate['id']}"
        assert client.post(f"{url}/render", json={
            "expected_revision": candidate["revision"],
        }).status_code == 409
        if candidate == candidates[0]:
            invalid = client.patch(url, json={
                "expected_revision": candidate["revision"], "action": "edit",
                "start_ms": 9500,
            })
            assert invalid.status_code == 422
            edited = client.patch(url, json={
                "expected_revision": candidate["revision"], "action": "edit",
                "aspect": "vertical", "focus_x": 0.7,
            })
            assert edited.status_code == 200, edited.text
            candidate = edited.json()
        selected = client.patch(url, json={
            "expected_revision": candidate["revision"], "action": "select",
        })
        assert selected.status_code == 200, selected.text
        queued = client.post(f"{url}/render", json={
            "expected_revision": selected.json()["revision"],
        })
        assert queued.status_code == 202, queued.text
        assert media_one()
        render_job = client.get(f"/api/v1/jobs/{queued.json()['job_id']}").json()
        assert render_job["status"] == "SUCCEEDED", render_job["error"]
        assert render_job["result"]["captions"] >= 1
        downloaded = client.get(f"{url}/render/{render_job['id']}")
        assert downloaded.status_code == 200 and downloaded.content
        if first_download is None:
            first_download = f"{url}/render/{render_job['id']}"
        outputs.append((candidate["id"], render_job["result"]["sha256"]))
    assert len({item[1] for item in outputs}) == 2
    assert first_download is not None
    words[0]["text"] = "corrigido"
    edited_transcript = client.put(transcript_url, json={
        "expected_revision": 2, "language": "pt", "words": words, "cues": cues,
    })
    assert edited_transcript.status_code == 200
    assert client.get(first_download).status_code == 409
    assert client.get(f"/api/v1/assets/{asset_id}/clips").status_code == 409
