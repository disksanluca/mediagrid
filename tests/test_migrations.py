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
            "0002_revisions",
        )
        saved_edl = connection.execute(
            "SELECT edl FROM projects WHERE id=?", (project_id,)
        ).fetchone()[0]
        assert '"version": 1' in saved_edl
        assert connection.execute("SELECT COUNT(*) FROM project_revisions").fetchone() == (0,)
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
