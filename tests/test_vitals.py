from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.monitoring.analysis import summarize
from app.monitoring.metrics import METRICS


def make_patient(client, name="Asha Sharma", email=None) -> int:
    payload = {"full_name": name, "age": 52, "gender": "Female", "email": email}
    return client.post("/patients", json=payload).json()["id"]


def reading(days_ago: float, **values):
    base = {key: None for key in METRICS}
    when = datetime(2026, 11, 1, tzinfo=UTC) - timedelta(days=days_ago)
    return SimpleNamespace(recorded_at=when, **(base | values))


def by_metric(summaries):
    return {s.metric: s for s in summaries}


# --- analysis ---------------------------------------------------------------


def test_range_flags():
    result = by_metric(summarize([reading(0, glucose=190, spo2=91, heart_rate=72)]))
    assert result["glucose"].status == "high"
    assert result["spo2"].status == "low"
    assert result["heart_rate"].status == "normal"
    assert result["weight_kg"].status == "no-data"
    assert any("Glucose 190" in a for a in result["glucose"].alerts)


def test_personal_baseline_outlier_even_when_in_range():
    history = [reading(10 - i, heart_rate=hr) for i, hr in enumerate([60, 61, 59, 60, 62, 61])]
    history.append(reading(0, heart_rate=95))  # still < 100, but far above this baseline
    hr = by_metric(summarize(history))["heart_rate"]
    assert hr.status == "normal"
    assert hr.outlier and hr.robust_z > 3.5
    assert "unusually higher" in hr.alerts[0]


def test_no_outlier_without_enough_history_or_spread():
    few = [reading(3 - i, glucose=100) for i in range(3)] + [reading(0, glucose=130)]
    assert not by_metric(summarize(few))["glucose"].outlier
    flat = [reading(9 - i, glucose=100) for i in range(8)] + [reading(0, glucose=130)]
    assert by_metric(summarize(flat))["glucose"].robust_z is None  # MAD is zero


def test_trend_slope_per_30_days():
    rising = [reading(30 - d, glucose=100 + d) for d in range(0, 31, 5)]  # +1 per day
    glucose = by_metric(summarize(rising))["glucose"]
    assert abs(glucose.trend_per_30d - 30) < 0.01
    assert glucose.trend_r2 > 0.99


# --- API --------------------------------------------------------------------


def test_record_list_and_analyse(client):
    patient_id = make_patient(client)
    now = datetime.now(UTC)
    for i, glucose in enumerate([95, 97, 99, 101]):
        response = client.post(
            f"/patients/{patient_id}/vitals",
            json={
                "recorded_at": (now - timedelta(days=4 - i)).isoformat(),
                "glucose": glucose,
                "systolic_bp": 120,
                "diastolic_bp": 80,
            },
        )
        assert response.status_code == 201
    latest = client.post(f"/patients/{patient_id}/vitals", json={"glucose": 160})
    assert latest.json()["source"] == "manual"

    readings = client.get(f"/patients/{patient_id}/vitals").json()
    assert [r["glucose"] for r in readings] == [95, 97, 99, 101, 160]

    analysis = client.get(f"/patients/{patient_id}/vitals/analysis").json()
    assert analysis["readings"] == 5
    glucose = next(m for m in analysis["metrics"] if m["metric"] == "glucose")
    assert glucose["status"] == "high" and glucose["latest"] == 160
    assert glucose["trend_per_30d"] > 0
    assert any("Glucose" in a for a in analysis["alerts"])


def test_validation(client):
    patient_id = make_patient(client)
    url = f"/patients/{patient_id}/vitals"
    assert client.post(url, json={}).status_code == 422
    assert client.post(url, json={"glucose": 5000}).status_code == 422
    assert client.post(url, json={"systolic_bp": 80, "diastolic_bp": 90}).status_code == 422
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert client.post(url, json={"glucose": 100, "recorded_at": future}).status_code == 422
    assert client.post(url, json={"glucose": 100, "bmi": 22}).status_code == 422
    assert client.post("/patients/999/vitals", json={"glucose": 100}).status_code == 404


def test_demo_data_and_alerts_overview(client):
    worsening = make_patient(client, "Asha Sharma", "a@example.com")
    stable = make_patient(client, "Ravi Kumar", "r@example.com")
    inactive = make_patient(client, "Meera Iyer", "m@example.com")
    assert client.post(f"/patients/{worsening}/vitals/demo").json() == {"created": 30}
    client.post(f"/patients/{stable}/vitals/demo", json={"profile": "stable", "days": 14})
    client.post(f"/patients/{inactive}/vitals/demo")
    client.delete(f"/patients/{inactive}")

    analysis = client.get(f"/patients/{worsening}/vitals/analysis").json()
    glucose = next(m for m in analysis["metrics"] if m["metric"] == "glucose")
    assert glucose["status"] == "high" and glucose["outlier"] and glucose["trend_per_30d"] > 0

    overview = client.get("/monitoring/alerts").json()
    assert [p["patient_id"] for p in overview] == [worsening]
    assert overview[0]["full_name"] == "Asha Sharma"
    assert client.get(f"/patients/{stable}/vitals", params={"days": 7}).json()
