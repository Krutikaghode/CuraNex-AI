import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.session import build_engine, get_db
from app.main import app
from app.services import users

ADMIN = {"email": "admin@example.com", "password": "Admin-pass-123"}
CLINICIAN = {"email": "doc@example.com", "password": "Doctor-pass-123"}


@pytest.fixture()
def anon_client(tmp_path, monkeypatch):
    """A client with an isolated database and no credentials."""
    monkeypatch.setattr(get_settings(), "data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(get_settings(), "llm_provider", "fake")
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    with TestingSession() as db:
        users.create_user(db, full_name="Admin", role="admin", **ADMIN)
        users.create_user(db, full_name="Doctor", role="clinician", **CLINICIAN)

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/token", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def client(anon_client):
    """Signed in as a clinician; most tests use this."""
    anon_client.headers.update(login(anon_client, **CLINICIAN))
    return anon_client
