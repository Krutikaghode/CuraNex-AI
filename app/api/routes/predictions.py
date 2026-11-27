"""Disease-risk prediction endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Prediction
from app.db.session import get_db
from app.ml.diabetes import DiabetesModel, ModelNotAvailableError, get_diabetes_model
from app.schemas.prediction import DiabetesInput, ModelInfo, PredictionResponse, RiskSummary
from app.services import patients as patient_service
from app.services import predictions as service

router = APIRouter(tags=["predictions"])


def diabetes_model() -> DiabetesModel:
    try:
        return get_diabetes_model()
    except ModelNotAvailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/models/diabetes", response_model=ModelInfo)
def diabetes_model_info(model: DiabetesModel = Depends(diabetes_model)) -> dict:
    return model.metadata


@router.post(
    "/patients/{patient_id}/predictions/diabetes",
    response_model=PredictionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_diabetes_prediction(
    patient_id: int,
    payload: DiabetesInput,
    db: Session = Depends(get_db),
    model: DiabetesModel = Depends(diabetes_model),
) -> Prediction:
    patient = patient_service.get_patient(db, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} was not found.")
    return service.predict_diabetes(db, patient, payload.model_dump(), model)


@router.get("/patients/{patient_id}/predictions", response_model=list[PredictionResponse])
def patient_predictions(patient_id: int, db: Session = Depends(get_db)) -> list[Prediction]:
    if patient_service.get_patient(db, patient_id, include_inactive=True) is None:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} was not found.")
    return service.list_for_patient(db, patient_id)


@router.get("/predictions/summary", response_model=RiskSummary)
def prediction_summary(db: Session = Depends(get_db)) -> dict:
    return service.risk_summary(db)
