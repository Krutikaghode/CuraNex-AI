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

    updated = client.patch("/patients/1", json={"age": 35, "concern": "Annual screening"})
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
    duplicate = client.post("/patients", json=patient_payload(full_name="Nisha Patel"))
    assert duplicate.status_code == 409


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}


def test_search_and_include_inactive(client):
    client.post("/patients", json=patient_payload())
    client.post(
        "/patients",
        json=patient_payload(full_name="Ravi Kumar", email="ravi@example.com"),
    )
    assert [p["full_name"] for p in client.get("/patients", params={"search": "ravi"}).json()] == [
        "Ravi Kumar"
    ]
    client.delete("/patients/1")
    assert len(client.get("/patients").json()) == 1
    assert len(client.get("/patients", params={"include_inactive": True}).json()) == 2
    assert client.delete("/patients/1").status_code == 404


def test_update_to_duplicate_email_conflicts(client):
    client.post("/patients", json=patient_payload())
    client.post("/patients", json=patient_payload(full_name="Ravi Kumar", email="ravi@example.com"))
    response = client.patch("/patients/2", json={"email": "ASHA@example.com"})
    assert response.status_code == 409


def test_unknown_fields_rejected(client):
    assert client.post("/patients", json=patient_payload(ssn="123")).status_code == 422
