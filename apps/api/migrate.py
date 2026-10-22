"""Bootstrap the existing schema once, then apply reviewed Alembic revisions."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect

from . import models  # noqa: F401
from .config import get_settings
from .database import Base, engine

LEGACY_TABLES = (
    "channels", "projects", "assets", "jobs", "events", "platform_connections"
)


def _config() -> Config:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    return config


def _backup_existing_sqlite() -> None:
    if engine.dialect.name != "sqlite" or not engine.url.database:
        return
    source_path = Path(engine.url.database).resolve()
    if not source_path.is_file():
        return
    backup_dir = get_settings().mediagrid_data_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target_path = backup_dir / f"pre-edl-v2-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.db"
    with sqlite3.connect(source_path) as source, sqlite3.connect(target_path) as target:
        source.backup(target)


def main() -> None:
    settings = get_settings()
    settings.mediagrid_data_dir.mkdir(parents=True, exist_ok=True)
    for directory in ("assets", "exports", "renders", "temp", "voice", "transcripts", "backups"):
        (settings.mediagrid_data_dir / directory).mkdir(exist_ok=True)
    existing = set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        revision = MigrationContext.configure(connection).get_current_revision()
    if revision is None:
        present = existing.intersection(LEGACY_TABLES)
        if present and present != set(LEGACY_TABLES):
            raise RuntimeError(f"Incomplete legacy MediaGrid schema: {sorted(present)}")
        if present:
            inspector = inspect(engine)
            for name in LEGACY_TABLES:
                actual = {column["name"] for column in inspector.get_columns(name)}
                expected = {column.name for column in Base.metadata.tables[name].columns}
                if missing := expected - actual:
                    raise RuntimeError(f"Legacy table {name} is missing columns: {sorted(missing)}")
            _backup_existing_sqlite()
        else:
            Base.metadata.create_all(
                bind=engine, tables=[Base.metadata.tables[name] for name in LEGACY_TABLES]
            )
        command.stamp(_config(), "0001_legacy")
    command.upgrade(_config(), "head")


if __name__ == "__main__":
    main()
