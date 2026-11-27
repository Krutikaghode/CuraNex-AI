"""Run models for patients and persist the results."""

from dataclasses import asdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Patient, Prediction
from app.ml.diabetes import DiabetesModel
from app.ml.features import FEATURE_LABELS

DIABETES = "diabetes"


def predict_diabetes(
    db: Session, patient: Patient, inputs: dict, model: DiabetesModel
) -> Prediction:
    inputs = dict(inputs)
    if inputs.get("age") is None:
        inputs["age"] = patient.age
    result = model.predict(inputs)
    prediction = Prediction(
        patient_id=patient.id,
        disease=DIABETES,
        model_name=model.name,
        model_version=model.version,
        inputs=inputs,
        probability=result.probability,
        risk_level=result.risk_level,
        contributions=[
            {**asdict(item), "label": FEATURE_LABELS[item.feature]} for item in result.contributions
        ],
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


def list_for_patient(db: Session, patient_id: int, limit: int = 50) -> list[Prediction]:
    query = (
        select(Prediction)
        .where(Prediction.patient_id == patient_id)
        .order_by(Prediction.created_at.desc(), Prediction.id.desc())
        .limit(limit)
    )
    return list(db.scalars(query))


def risk_summary(db: Session, disease: str = DIABETES) -> dict:
    """Count active patients by the risk level of their most recent prediction."""
    latest = (
        select(func.max(Prediction.id).label("id"))
        .where(Prediction.disease == disease)
        .group_by(Prediction.patient_id)
        .subquery()
    )
    query = (
        select(Prediction.risk_level, func.count())
        .join(latest, Prediction.id == latest.c.id)
        .join(Patient, Patient.id == Prediction.patient_id)
        .where(Patient.is_active.is_(True))
        .group_by(Prediction.risk_level)
    )
    counts = {level: count for level, count in db.execute(query)}
    return {"disease": disease, **counts, "patients_scored": sum(counts.values())}
