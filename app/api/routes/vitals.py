"""Vital signs and health monitoring."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.models import Patient, VitalReading
from app.db.session import get_db
from app.schemas.vitals import DemoRequest, PatientAlerts, VitalCreate, VitalOut, VitalsAnalysis
from app.services import patients as patient_service
from app.services import vitals as service

router = APIRouter(tags=["monitoring"])


def _patient(db: Session, patient_id: int, include_inactive: bool = False) -> Patient:
    patient = patient_service.get_patient(db, patient_id, include_inactive=include_inactive)
    if patient is None:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} was not found.")
    return patient


@router.post(
    "/patients/{patient_id}/vitals", response_model=VitalOut, status_code=status.HTTP_201_CREATED
)
def record_vitals(
    patient_id: int, payload: VitalCreate, db: Session = Depends(get_db)
) -> VitalReading:
    return service.record(db, _patient(db, patient_id), payload.model_dump())


@router.get("/patients/{patient_id}/vitals", response_model=list[VitalOut])
def list_vitals(
    patient_id: int,
    days: int | None = Query(default=None, ge=1, le=3650),
    db: Session = Depends(get_db),
) -> list[VitalReading]:
    _patient(db, patient_id, include_inactive=True)
    return service.list_readings(db, patient_id, days)


@router.get("/patients/{patient_id}/vitals/analysis", response_model=VitalsAnalysis)
def analyse_vitals(
    patient_id: int,
    days: int = Query(default=30, ge=1, le=3650),
    db: Session = Depends(get_db),
) -> dict:
    _patient(db, patient_id, include_inactive=True)
    return service.analyse(db, patient_id, days)


@router.post("/patients/{patient_id}/vitals/demo", status_code=status.HTTP_201_CREATED)
def generate_demo_vitals(
    patient_id: int, payload: DemoRequest | None = None, db: Session = Depends(get_db)
) -> dict:
    payload = payload or DemoRequest()
    created = service.generate_demo(db, _patient(db, patient_id), payload.days, payload.profile)
    return {"created": created}


@router.get("/monitoring/alerts", response_model=list[PatientAlerts])
def monitoring_alerts(
    days: int = Query(default=30, ge=1, le=3650), db: Session = Depends(get_db)
) -> list[dict]:
    return service.alerts_overview(db, days)
