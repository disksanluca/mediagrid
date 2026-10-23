import hashlib
import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./data/mediagrid-test.db"
Path("data").mkdir(exist_ok=True)

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from apps.api.config import get_settings  # noqa: E402
from apps.api.database import Base, SessionLocal, engine  # noqa: E402
from apps.api.main import app  # noqa: E402
from apps.api.migrate import _config  # noqa: E402
from apps.api.models import Job, JobStatus, Project, ProjectStatus, now  # noqa: E402
from apps.api.routes.projects import latest_revision, legacy_hash  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    Base.metadata.create_all(bind=engine)
    command.stamp(_config(), "head")
    yield
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seed_completed_render():
    """Record a synthetic MP4 and its worker hash for review-route tests."""
    def seed(project_id: str, content: bytes) -> Path:
        output = get_settings().mediagrid_data_dir / "renders" / f"{project_id}.mp4"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
        with SessionLocal() as db:
            project = db.get(Project, project_id)
            assert project is not None and project.edl
            revision = latest_revision(db, project_id)
            result = {
                "output": str(output),
                "sha256": hashlib.sha256(content).hexdigest(),
                "edl_sha256": legacy_hash(project.edl),
            }
            if revision:
                result["revision_sha256"] = revision.sha256
            db.add(Job(
                project_id=project_id, job_type="RENDER",
                status=JobStatus.SUCCEEDED.value, result=result,
                finished_at=now(), progress=1,
            ))
            project.status = ProjectStatus.QC.value
            db.commit()
        return output
    return seed
