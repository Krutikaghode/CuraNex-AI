from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.main import app
from backend import database


@pytest.fixture()
def client(monkeypatch):
    test_db = Path("data") / "test_curanex.db"
    if test_db.exists():
        test_db.unlink()
    monkeypatch.setattr(database, "DB_PATH", test_db)
    with TestClient(app) as test_client:
        yield test_client
    if test_db.exists():
        test_db.unlink()


def patient_payload(**overrides):
    payload = {
        "full_name": "Asha Sharma",
        "age": 34,
        "gender": "Female",
        "email": "asha@example.com",
        "phone": "9876543210",
        "concern": "Routine screening",
    }
    payload.update(overrides)
    return payload


def test_patient_lifecycle(client):
    created = client.post("/patients", json=patient_payload())
    assert created.status_code == 201
    patient = created.json()
    assert patient["id"] == 1
    assert patient["is_active"] is True

    listed = client.get("/patients")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert client.get("/patients/count").json() == {"count": 1}

    updated = client.patch(
        "/patients/1", json={"age": 35, "concern": "Annual screening"}
    )
    assert updated.status_code == 200
    assert updated.json()["age"] == 35

    deactivated = client.delete("/patients/1")
    assert deactivated.status_code == 204
    assert client.get("/patients/1").status_code == 404
    assert client.get("/patients/count").json() == {"count": 0}

    restored = client.patch("/patients/1/restore")
    assert restored.status_code == 200
    assert restored.json()["is_active"] is True


def test_patient_validation_and_duplicate_email(client):
    invalid = client.post("/patients", json=patient_payload(age=200))
    assert invalid.status_code == 422

    first = client.post("/patients", json=patient_payload())
    assert first.status_code == 201
    duplicate = client.post(
        "/patients", json=patient_payload(full_name="Nisha Patel")
    )
    assert duplicate.status_code == 409
