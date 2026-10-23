"""The destructive migration smoke may target only the CI service database."""

import pytest

from scripts.smoke_postgres_migrations import validate_target


def test_postgres_smoke_requires_ephemeral_local_target() -> None:
    allowed = "postgresql+psycopg://postgres:ci-only@127.0.0.1:5432/mediagrid_ci"
    validate_target(allowed, "1")
    for url, enabled in (
        (allowed, None),
        ("postgresql+psycopg://postgres:x@remote.example/mediagrid_ci", "1"),
        ("postgresql+psycopg://postgres:x@127.0.0.1/mediagrid", "1"),
        ("sqlite:///./data/mediagrid.db", "1"),
    ):
        with pytest.raises(RuntimeError, match="ephemeral CI database"):
            validate_target(url, enabled)
    restored = allowed.replace("/mediagrid_ci", "/mediagrid_restored")
    validate_target(restored, "1", database_name="mediagrid_restored")
    with pytest.raises(RuntimeError):
        validate_target(allowed, "1", database_name="production")
