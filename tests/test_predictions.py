from pathlib import Path

import pytest

from app.ml.diabetes import DiabetesModel, ModelNotAvailableError, get_diabetes_model
from app.ml.features import FEATURES, risk_level

HEALTHY = {"glucose": 85, "bmi": 22.0, "age": 25, "blood_pressure": 70, "pregnancies": 0}
AT_RISK = {"glucose": 190, "bmi": 41.0, "age": 55, "blood_pressure": 85, "pregnancies": 6}


def make_patient(client, **overrides) -> int:
    payload = {"full_name": "Asha Sharma", "age": 40, "gender": "Female", **overrides}
    return client.post("/patients", json=payload).json()["id"]


def test_shipped_model_meets_quality_floor():
    model = get_diabetes_model()
    assert model.metadata["features"] == FEATURES
    assert model.metadata["metrics"]["roc_auc"] >= 0.75


def test_model_info_endpoint(client):
    body = client.get("/models/diabetes").json()
    assert body["name"] == "diabetes-xgboost"
    assert set(body["metrics"]) >= {"roc_auc", "accuracy", "recall"}


def test_risk_bands():
    assert risk_level(0.1) == "low"
    assert risk_level(0.45) == "moderate"
    assert risk_level(0.9) == "high"


def test_prediction_separates_healthy_from_at_risk(client):
    patient_id = make_patient(client)
    low = client.post(f"/patients/{patient_id}/predictions/diabetes", json=HEALTHY)
    high = client.post(f"/patients/{patient_id}/predictions/diabetes", json=AT_RISK)
    assert low.status_code == high.status_code == 201
    assert low.json()["risk_level"] == "low"
    assert high.json()["risk_level"] == "high"
    assert high.json()["probability"] > low.json()["probability"]

    top = high.json()["contributions"][0]
    assert top["feature"] in FEATURES and top["impact"] > 0
    assert top["label"]


def test_optional_fields_and_age_default(client):
    patient_id = make_patient(client, age=61)
    response = client.post(
        f"/patients/{patient_id}/predictions/diabetes", json={"glucose": 140, "bmi": 30}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["inputs"]["age"] == 61
    insulin = next(c for c in body["contributions"] if c["feature"] == "insulin")
    assert insulin["value"] is None


def test_prediction_validation_and_missing_patient(client):
    patient_id = make_patient(client)
    url = f"/patients/{patient_id}/predictions/diabetes"
    assert client.post(url, json={"glucose": 0, "bmi": 30}).status_code == 422
    assert client.post(url, json={"bmi": 30}).status_code == 422
    assert client.post(url, json={**HEALTHY, "cholesterol": 200}).status_code == 422
    assert client.post("/patients/999/predictions/diabetes", json=HEALTHY).status_code == 404


def test_history_and_summary_use_latest_per_active_patient(client):
    first = make_patient(client, email="a@example.com")
    second = make_patient(client, full_name="Ravi Kumar", email="r@example.com")
    third = make_patient(client, full_name="Meera Iyer", email="m@example.com")

    client.post(f"/patients/{first}/predictions/diabetes", json=AT_RISK)
    client.post(f"/patients/{first}/predictions/diabetes", json=HEALTHY)  # latest wins
    client.post(f"/patients/{second}/predictions/diabetes", json=AT_RISK)
    client.post(f"/patients/{third}/predictions/diabetes", json=AT_RISK)
    client.delete(f"/patients/{third}")  # inactive patients are excluded

    history = client.get(f"/patients/{first}/predictions").json()
    assert [p["risk_level"] for p in history] == ["low", "high"]

    summary = client.get("/predictions/summary").json()
    assert summary == {
        "disease": "diabetes",
        "low": 1,
        "moderate": 0,
        "high": 1,
        "patients_scored": 2,
    }
    assert client.get("/patients/999/predictions").status_code == 404


def test_missing_model_artifact(tmp_path: Path):
    with pytest.raises(ModelNotAvailableError):
        DiabetesModel(tmp_path)


def test_missing_model_returns_503(client):
    from app.api.routes.predictions import diabetes_model
    from app.main import app

    def unavailable():
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="No diabetes model")

    app.dependency_overrides[diabetes_model] = unavailable
    assert client.get("/models/diabetes").status_code == 503
