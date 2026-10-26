"""Exercise real Alembic and portable backup only in pytest's disposable directory."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apps.api.backup import create_backup, restore_backup
from apps.api.models import Channel, Job, MotionArtifactReview, Project


def test_motion_review_upgrade_backup_restore_and_guarded_downgrade(tmp_path):
    root = Path(__file__).resolve().parents[1]
    data = tmp_path / "Data"
    database = data / "Database" / "mediagrid.db"
    database.parent.mkdir(parents=True)
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{database.as_posix()}",
        "MEDIAGRID_DATA_DIR": str(data),
    }

    def migrate(*args, check=True):
        return subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=check,
        )

    subprocess.run(
        [sys.executable, "-m", "apps.api.migrate"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    migrate("downgrade", "0012_creative_direction")
    isolated = create_engine(env["DATABASE_URL"])
    with Session(isolated) as db:
        channel = Channel(name="Preserved", slug="preserved", niche="Test", default_engine="geo")
        db.add(channel)
        db.flush()
        project = Project(
            channel_id=channel.id,
            title="Legacy title",
            topic="Synthetic",
            edl={"version": 1, "tracks": {}},
        )
        db.add(project)
        db.flush()
        job = Job(project_id=project.id, job_type="CREATIVE_MOTION")
        db.add(job)
        db.commit()
        project_id, job_id = project.id, job.id
    migrate("upgrade", "head")
    with Session(isolated) as db:
        db.add(
            MotionArtifactReview(
                project_id=project_id,
                job_id=job_id,
                revision=1,
                request_sha256="a" * 64,
                plan_sha256="b" * 64,
                video_sha256="c" * 64,
                snapshot_sha256="d" * 64,
                dependencies_sha256="e" * 64,
                decision="REQUEST_REVIEW",
                actor="isolated-test",
                notes="Persistence fixture, not an audiovisual approval",
            )
        )
        db.commit()
    isolated.dispose()
    media = data / "creative-renders" / f"{job_id}.mp4"
    media.parent.mkdir()
    media.write_bytes(b"backup test hash fixture, not a real MP4")
    archive = tmp_path / "isolated.mgrid"
    manifest = create_backup(data, archive)
    assert any("creative-renders" in f["path"] for f in manifest["files"])
    restored = tmp_path / "Restored"
    restore_backup(restored, archive)
    assert (restored / "creative-renders" / media.name).read_bytes() == media.read_bytes()
    with sqlite3.connect(restored / "Database/mediagrid.db") as db:
        assert db.execute("SELECT title FROM projects").fetchone() == ("Legacy title",)
        assert db.execute(
            "SELECT decision, video_sha256 FROM motion_artifact_reviews"
        ).fetchone() == (
            "REQUEST_REVIEW",
            "c" * 64,
        )
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0013_motion_artifact_review",
        )
    blocked = migrate("downgrade", "0012_creative_direction", check=False)
    assert blocked.returncode != 0 and "human review history" in blocked.stderr
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT count(*) FROM motion_artifact_reviews").fetchone() == (1,)
