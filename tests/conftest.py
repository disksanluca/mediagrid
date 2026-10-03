import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./data/mediagrid-test.db"
Path("data").mkdir(exist_ok=True)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from apps.api.database import Base, engine  # noqa: E402
from apps.api.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
