"""Server topology must fail closed until its prerequisites are configured."""

import pytest

from apps.api.config import Settings, get_settings
from apps.api.main import validate_runtime_config
from workers.render.main import main as local_worker_main


def server_settings(**overrides) -> Settings:
    values = {
        "mediagrid_mode": "SERVER",
        "mediagrid_server_experimental": True,
        "database_url": "postgresql+psycopg://user:secret@localhost/mediagrid",
        "mediagrid_admin_password": "private-admin-password",
        "mediagrid_session_secret": "private-session-secret",
        "mediagrid_public_url": "https://mediagrid.example",
        "allow_paid_ai": False,
        "dry_run": True,
    }
    values.update(overrides)
    return Settings(**values)


def test_server_configuration_fails_closed() -> None:
    validate_runtime_config(server_settings())
    for values, message in [
        ({"database_url": "sqlite:///./data/mediagrid.db"}, "PostgreSQL"),
        ({"mediagrid_public_url": "http://mediagrid.example"}, "HTTPS"),
        ({"mediagrid_admin_password": None}, "ADMIN_PASSWORD"),
        ({"allow_paid_ai": True}, "ALLOW_PAID_AI"),
        ({"dry_run": False}, "DRY_RUN"),
        ({"mediagrid_server_experimental": False}, "experimental"),
    ]:
        with pytest.raises(RuntimeError, match=message):
            validate_runtime_config(server_settings(**values))
    validate_runtime_config(Settings(mediagrid_mode="LOCAL"))


def test_local_worker_refuses_server_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "mediagrid_mode", "SERVER")
    with pytest.raises(RuntimeError, match="cannot process server jobs"):
        local_worker_main(["--once"])
