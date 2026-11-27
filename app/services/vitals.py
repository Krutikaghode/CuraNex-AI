"""Record, list, analyse and simulate vital signs."""

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Patient, VitalReading
from app.monitoring.analysis import summarize


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def record(db: Session, patient: Patient, values: dict, source: str = "manual") -> VitalReading:
    values = dict(values)
    values["recorded_at"] = values.get("recorded_at") or datetime.now(UTC)
    reading = VitalReading(patient_id=patient.id, source=source, **values)
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading


def list_readings(db: Session, patient_id: int, days: int | None = None) -> list[VitalReading]:
    query = select(VitalReading).where(VitalReading.patient_id == patient_id)
    if days:
        query = query.where(VitalReading.recorded_at >= datetime.now(UTC) - timedelta(days=days))
    return list(db.scalars(query.order_by(VitalReading.recorded_at, VitalReading.id)))


def analyse(db: Session, patient_id: int, days: int) -> dict:
    readings = list_readings(db, patient_id, days)
    for reading in readings:  # SQLite drops tzinfo; normalise before arithmetic
        reading.recorded_at = _aware(reading.recorded_at)
    summaries = summarize(readings)
    return {
        "patient_id": patient_id,
        "window_days": days,
        "readings": len(readings),
        "alerts": [alert for s in summaries for alert in s.alerts],
        "metrics": [asdict(s) for s in summaries],
    }


def alerts_overview(db: Session, days: int = 30) -> list[dict]:
    """Active patients whose recent vitals raise at least one alert, most recent first."""
    latest = (
        select(VitalReading.patient_id, func.max(VitalReading.recorded_at).label("latest"))
        .group_by(VitalReading.patient_id)
        .subquery()
    )
    rows = db.execute(
        select(Patient, latest.c.latest)
        .join(latest, latest.c.patient_id == Patient.id)
        .where(Patient.is_active.is_(True))
        .order_by(latest.c.latest.desc())
    ).all()
    overview = []
    for patient, latest_at in rows:
        alerts = analyse(db, patient.id, days)["alerts"]
        if alerts:
            overview.append(
                {
                    "patient_id": patient.id,
                    "full_name": patient.full_name,
                    "latest_reading_at": _aware(latest_at),
                    "alerts": alerts,
                }
            )
    return overview


def generate_demo(db: Session, patient: Patient, days: int, profile: str) -> int:
    """Insert one synthetic reading per day. 'worsening' drifts glucose and BP upward and
    ends with an abnormal reading so every alert type can be demonstrated."""
    rng = np.random.default_rng(patient.id)
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    drift = 1.0 if profile == "worsening" else 0.0
    for day in range(days):
        progress = day / max(days - 1, 1)
        is_last = day == days - 1
        glucose = 98 + drift * 25 * progress + rng.normal(0, 5)
        systolic = 118 + drift * 12 * progress + rng.normal(0, 4)
        if is_last and drift:
            glucose, systolic = 182.0, 148.0
        db.add(
            VitalReading(
                patient_id=patient.id,
                recorded_at=now - timedelta(days=days - 1 - day),
                glucose=round(glucose, 1),
                systolic_bp=round(systolic),
                diastolic_bp=round(systolic * 0.64 + rng.normal(0, 2)),
                heart_rate=round(72 + drift * 6 * progress + rng.normal(0, 3)),
                spo2=round(min(100.0, 97.5 + rng.normal(0, 0.6)), 1),
                temperature_c=round(36.7 + rng.normal(0, 0.15), 1),
                weight_kg=round(68 + drift * 1.5 * progress + rng.normal(0, 0.3), 1),
                source="demo",
            )
        )
    db.commit()
    return days
