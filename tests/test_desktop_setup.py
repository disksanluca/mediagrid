from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.config import get_settings
from apps.api.hardware import choose_profile


def test_hardware_profile_uses_safe_resource_levels() -> None:
    assert choose_profile(None, None) == "LIGHT"
    assert choose_profile(16, 8) == "BALANCED"
    assert choose_profile(32, 16) == "QUALITY"
    assert choose_profile(64, 24) == "HIGH_PERFORMANCE"


def test_first_run_setup_is_saved_in_local_data(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MEDIAGRID_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        hardware = client.get("/api/v1/system/hardware")
        assert hardware.status_code == 200
        assert hardware.json()["recommended_profile"] in {
            "LIGHT", "BALANCED", "QUALITY", "HIGH_PERFORMANCE"
        }
        initial = client.get("/api/v1/system/setup").json()
        assert initial["complete"] is False
        assert initial["data_dir"] == str(tmp_path)
        saved = client.post("/api/v1/system/setup", json={"profile": "LIGHT"})
        assert saved.status_code == 200
        assert saved.json()["complete"] is True
        assert (tmp_path / "settings.json").is_file()
        assert client.get("/api/v1/system/setup").json()["profile"] == "LIGHT"
    finally:
        get_settings.cache_clear()
