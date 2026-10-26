"""Exercise all Alembic revisions and a leased claim on an ephemeral CI database."""

import os

from sqlalchemy.engine import make_url


def validate_target(database_url: str, enabled: str | None,
                    *, database_name: str = "mediagrid_ci") -> None:
    url = make_url(database_url)
    if database_name not in {"mediagrid_ci", "mediagrid_restored"}:
        raise RuntimeError("PostgreSQL smoke target is not an ephemeral CI database")
    if (enabled != "1" or url.drivername != "postgresql+psycopg"
            or url.host not in {"127.0.0.1", "localhost"}
            or url.database != database_name):
        raise RuntimeError("PostgreSQL smoke requires the opt-in ephemeral CI database")


def main() -> None:
    validate_target(os.environ.get("DATABASE_URL", ""),
                    os.environ.get("MEDIAGRID_ALLOW_EPHEMERAL_PG_SMOKE"))

    from alembic import command
    from sqlalchemy import inspect, select, text

    from apps.api.database import Base, SessionLocal, engine
    from apps.api.migrate import _config
    from apps.api.models import Channel, Job, JobStatus, MotionArtifactReview, Project
    from apps.api.services import claim_next_job, fence_job_completion, renew_job_lease

    if inspect(engine).get_table_names():
        raise RuntimeError("PostgreSQL smoke database must start empty")

    Base.metadata.create_all(bind=engine)
    command.stamp(_config(), "head")
    with SessionLocal() as db:
        channel = Channel(name="Canal CI", slug="canal-ci", niche="Teste",
                          default_engine="politics")
        db.add(channel)
        db.flush()
        project = Project(channel_id=channel.id, title="Dado preservado — CI",
                          topic="Pauta sintética de migração", format="vertical",
                          edl={"version": 1, "tracks": {"video": []}})
        db.add(project)
        db.flush()
        job = Job(project_id=project.id, job_type="RENDER", payload={"synthetic": True})
        db.add(job)
        db.commit()
        project_id, job_id = project.id, job.id

    command.downgrade(_config(), "0001_legacy")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0001_legacy"
        )
        assert "lease_owner" not in {
            column["name"] for column in inspect(connection).get_columns("jobs")
        }
        assert connection.scalar(text("SELECT title FROM projects WHERE id=:id"),
                                 {"id": project_id}) == "Dado preservado — CI"

    command.upgrade(_config(), "head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0013_motion_artifact_review"
        )
        assert {"lease_owner", "lease_expires_at", "heartbeat_at"} <= {
            column["name"] for column in inspect(connection).get_columns("jobs")
        }
        claim_columns = {
            column["name"]: column for column in
            inspect(connection).get_columns("knowledge_claims")
        }
        assert claim_columns["published_at"]["nullable"]
        assert claim_columns["source_checked_at"]["nullable"]
        assert "music_draft_schedules" in inspect(connection).get_table_names()
        assert {"creative_dna_revisions", "creative_briefs", "creative_direction_sets",
                "creative_storyboard_revisions", "creative_reviews", "motion_artifact_reviews"} <= (
            set(inspect(connection).get_table_names())
        )

    with SessionLocal() as first, SessionLocal() as second:
        project = first.get(Project, project_id)
        assert project is not None and project.title == "Dado preservado — CI"
        claimed = claim_next_job(first, "RENDER", worker_id="ci-first")
        assert claimed is not None and claimed.id == job_id
        token = claimed.lease_owner
        assert token and token.startswith("ci-first:")
        assert claim_next_job(second, "RENDER", worker_id="ci-second") is None
        second.rollback()
        first.commit()

    with SessionLocal() as db:
        assert renew_job_lease(db, job_id, token)
        db.commit()
        claimed = db.scalar(select(Job).where(Job.id == job_id))
        assert claimed is not None
        claimed.status = JobStatus.SUCCEEDED.value
        claimed.result = {"synthetic": True}
        assert fence_job_completion(db, job_id, token)
        db.commit()
        db.refresh(claimed)
        assert claimed.status == JobStatus.SUCCEEDED.value
        assert claimed.lease_owner is None
        db.add(MotionArtifactReview(
            project_id=project_id, job_id=job_id, revision=1,
            request_sha256="a"*64, plan_sha256="b"*64, video_sha256="c"*64,
            snapshot_sha256="d"*64, dependencies_sha256="e"*64,
            decision="REQUEST_REVIEW", actor="synthetic-ci",
            notes="Database persistence fixture; no audiovisual approval",
        ))
        db.commit()

    print("PostgreSQL 16: legacy data, Alembic 0001→0013, SKIP LOCKED and lease passed")


if __name__ == "__main__":
    main()
