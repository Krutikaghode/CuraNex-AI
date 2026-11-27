"""Patient-management HTTP endpoints."""

from fastapi import APIRouter, HTTPException, Query, Response, status

from backend.database import (
    DuplicateEmailError,
    create_patient,
    deactivate_patient,
    get_patient,
    get_patient_count,
    list_patients,
    restore_patient,
    update_patient,
)
from backend.schemas.patient import (
    PatientCountResponse,
    PatientCreate,
    PatientResponse,
    PatientUpdate,
)


router = APIRouter(prefix="/patients", tags=["patients"])


def _not_found(patient_id: int) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Patient {patient_id} was not found.")


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def register_patient(payload: PatientCreate) -> dict:
    try:
        return create_patient(**payload.model_dump())
    except DuplicateEmailError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("", response_model=list[PatientResponse])
def get_patients(
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_inactive: bool = False,
) -> list[dict]:
    return list_patients(
        search=search,
        limit=limit,
        offset=offset,
        include_inactive=include_inactive,
    )


@router.get("/count", response_model=PatientCountResponse)
def patient_count(include_inactive: bool = False) -> dict[str, int]:
    return {"count": get_patient_count(include_inactive=include_inactive)}


@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient_by_id(patient_id: int, include_inactive: bool = False) -> dict:
    patient = get_patient(patient_id, include_inactive=include_inactive)
    if patient is None:
        raise _not_found(patient_id)
    return patient


@router.patch("/{patient_id}", response_model=PatientResponse)
def patch_patient(patient_id: int, payload: PatientUpdate) -> dict:
    try:
        patient = update_patient(patient_id, payload.model_dump(exclude_unset=True))
    except DuplicateEmailError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if patient is None:
        raise _not_found(patient_id)
    return patient


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_patient_by_id(patient_id: int) -> Response:
    if not deactivate_patient(patient_id):
        raise _not_found(patient_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{patient_id}/restore", response_model=PatientResponse)
def restore_patient_by_id(patient_id: int) -> dict:
    patient = restore_patient(patient_id)
    if patient is None:
        raise _not_found(patient_id)
    return patient
