"""Check that a pg_dump/pg_restore copy retained schema and baseline records."""

import os

from sqlalchemy import create_engine, inspect, text

from scripts.smoke_postgres_migrations import validate_target


def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    validate_target(database_url, os.environ.get("MEDIAGRID_ALLOW_EPHEMERAL_PG_SMOKE"),
                    database_name="mediagrid_restored")
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0009_job_leases"
        )
        assert {"channels", "projects", "jobs", "knowledge_claims", "narrative_3d"} <= (
            set(inspect(connection).get_table_names())
        )
        assert connection.scalar(text("SELECT COUNT(*) FROM channels")) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM projects")) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM jobs")) == 1
        assert connection.scalar(text("SELECT title FROM projects")) == "Dado preservado — CI"
        status, owner, result = connection.execute(text(
            "SELECT status, lease_owner, result FROM jobs"
        )).one()
        assert status == "SUCCEEDED" and owner is None
        assert result == {"synthetic": True}
    engine.dispose()
    print("PostgreSQL 16: pg_dump/pg_restore kept schema, data and completed job")


if __name__ == "__main__":
    main()
