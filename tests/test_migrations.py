"""Upgrade and rollback a copy of the legacy SQLite schema with existing content."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apps.api.database import Base
from apps.api.migrate import LEGACY_TABLES
from apps.api.models import Channel, Project


def test_legacy_database_upgrade_and_downgrade(tmp_path: Path) -> None:
    database = tmp_path / "mediagrid.db"
    legacy_engine = create_engine(f"sqlite:///{database.as_posix()}")
    Base.metadata.create_all(
        legacy_engine, tables=[Base.metadata.tables[name] for name in LEGACY_TABLES]
    )
    with Session(legacy_engine) as session:
        channel = Channel(name="Legado", slug="legado", niche="Teste", default_engine="clips")
        session.add(channel)
        session.flush()
        project = Project(
            channel_id=channel.id,
            title="Projeto preservado",
            topic="Tema original",
            edl={"version": 1, "tracks": {"video": [{"scene_id": "a", "duration": 3}]}},
        )
        session.add(project)
        session.commit()
        project_id = project.id
    legacy_engine.dispose()
    with sqlite3.connect(database) as connection:
        for column in ("lease_owner", "lease_expires_at", "heartbeat_at"):
            connection.execute(f"ALTER TABLE jobs DROP COLUMN {column}")

    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{database.as_posix()}",
        "MEDIAGRID_DATA_DIR": str(tmp_path),
    }
    subprocess.run(
        [sys.executable, "-m", "apps.api.migrate"],
        cwd=root, env=env, check=True, capture_output=True, text=True,
    )
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0010_geo_claim_source_dates",
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)")}
        assert {"lease_owner", "lease_expires_at", "heartbeat_at"} <= columns
        saved_edl = connection.execute(
            "SELECT edl FROM projects WHERE id=?", (project_id,)
        ).fetchone()[0]
        assert '"version": 1' in saved_edl
        assert connection.execute("SELECT COUNT(*) FROM project_revisions").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM upload_sessions").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM transcripts").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM transcript_words").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM clip_candidates").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM football_sequences").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM knowledge_claims").fetchone() == (0,)
        claim_columns = {row[1]: row[3] for row in connection.execute(
            "PRAGMA table_info(knowledge_claims)"
        )}
        assert claim_columns["published_at"] == 0
        assert claim_columns["source_checked_at"] == 0
        assert connection.execute("SELECT COUNT(*) FROM narrative_3d").fetchone() == (0,)
    assert len(list((tmp_path / "backups").glob("pre-edl-v2-*.db"))) == 1

    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "downgrade", "0001_legacy"],
        cwd=root, env=env, check=True, capture_output=True, text=True,
    )
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0001_legacy",
        )
        saved_title = connection.execute(
            "SELECT title FROM projects WHERE id=?", (project_id,)
        ).fetchone()
        assert saved_title == (
            "Projeto preservado",
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)")}
        assert not {"lease_owner", "lease_expires_at", "heartbeat_at"} & columns


def test_fresh_database_starts_at_current_schema(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{database.as_posix()}",
        "MEDIAGRID_DATA_DIR": str(tmp_path),
    }
    subprocess.run(
        [sys.executable, "-m", "apps.api.migrate"],
        cwd=root, env=env, check=True, capture_output=True, text=True,
    )
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0010_geo_claim_source_dates",
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)")}
        assert {"lease_owner", "lease_expires_at", "heartbeat_at"} <= columns
        assert connection.execute("SELECT COUNT(*) FROM narrative_3d").fetchone() == (0,)


def test_geo_source_date_migration_preserves_existing_claims(tmp_path: Path) -> None:
    database = tmp_path / "dated-claims.db"
    legacy_engine = create_engine(f"sqlite:///{database.as_posix()}")
    Base.metadata.create_all(
        legacy_engine, tables=[Base.metadata.tables[name] for name in LEGACY_TABLES]
    )
    legacy_engine.dispose()
    with sqlite3.connect(database) as connection:
        for column in ("lease_owner", "lease_expires_at", "heartbeat_at"):
            connection.execute(f"ALTER TABLE jobs DROP COLUMN {column}")
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{database.as_posix()}",
        "MEDIAGRID_DATA_DIR": str(tmp_path),
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "stamp", "0001_legacy"],
        cwd=root, env=env, check=True, capture_output=True, text=True,
    )
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "0009_job_leases"],
        cwd=root, env=env, check=True, capture_output=True, text=True,
    )
    with sqlite3.connect(database) as connection:
        connection.execute("""
            INSERT INTO knowledge_claims
            (id, project_id, scene_id, text, source_url, source_title,
             published_at, support_excerpt, revision, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "old-claim", "old-project", "scene-1", "Existing sourced claim",
            "https://example.org/source", "Existing source", "2025-05-01",
            "Existing excerpt with enough detail", 1, "APPROVED",
            "2025-05-02 00:00:00", "2025-05-02 00:00:00",
        ))
    subprocess.run(
        [sys.executable, "-m", "apps.api.migrate"],
        cwd=root, env=env, check=True, capture_output=True, text=True,
    )
    assert len(list((tmp_path / "backups").glob("pre-edl-v2-*.db"))) == 1
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT published_at, source_checked_at, status FROM knowledge_claims"
        ).fetchone() == ("2025-05-01", None, "APPROVED")
        columns = {row[1]: row[3] for row in connection.execute(
            "PRAGMA table_info(knowledge_claims)"
        )}
        assert columns["published_at"] == 0
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "downgrade",
         "0009_job_leases"],
        cwd=root, env=env, check=True, capture_output=True, text=True,
    )
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT published_at, status FROM knowledge_claims"
        ).fetchone() == ("2025-05-01", "APPROVED")
