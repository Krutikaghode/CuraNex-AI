"""Patient persistence logic, kept separate from HTTP concerns."""

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Patient

EDITABLE_FIELDS = {"full_name", "age", "gender", "email", "phone", "concern"}


class DuplicateEmailError(ValueError):
    """Raised when a supplied email is already assigned to a patient."""


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if "email" in str(error.orig).lower():
            raise DuplicateEmailError("This email is already registered.") from error
        raise


def create_patient(db: Session, **fields: Any) -> Patient:
    patient = Patient(**fields)
    db.add(patient)
    _commit(db)
    db.refresh(patient)
    return patient


def list_patients(
    db: Session,
    *,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_inactive: bool = False,
) -> list[Patient]:
    query = select(Patient)
    if not include_inactive:
        query = query.where(Patient.is_active.is_(True))
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Patient.full_name.ilike(term),
                Patient.email.ilike(term),
                Patient.phone.ilike(term),
            )
        )
    query = query.order_by(Patient.created_at.desc(), Patient.id.desc())
    return list(db.scalars(query.limit(limit).offset(offset)))


def get_patient(db: Session, patient_id: int, *, include_inactive: bool = False) -> Patient | None:
    patient = db.get(Patient, patient_id)
    if patient is None or (not include_inactive and not patient.is_active):
        return None
    return patient


def update_patient(db: Session, patient_id: int, changes: dict[str, Any]) -> Patient | None:
    patient = get_patient(db, patient_id)
    if patient is None:
        return None
    for field, value in changes.items():
        if field in EDITABLE_FIELDS:
            setattr(patient, field, value)
    _commit(db)
    db.refresh(patient)
    return patient


def set_active(db: Session, patient_id: int, active: bool) -> Patient | None:
    """Soft-delete or restore. Returns None if the patient is missing or already in that state."""
    patient = db.get(Patient, patient_id)
    if patient is None or patient.is_active == active:
        return None
    patient.is_active = active
    _commit(db)
    db.refresh(patient)
    return patient


def count_patients(db: Session, *, include_inactive: bool = False) -> int:
    query = select(func.count()).select_from(Patient)
    if not include_inactive:
        query = query.where(Patient.is_active.is_(True))
    return int(db.scalar(query) or 0)
