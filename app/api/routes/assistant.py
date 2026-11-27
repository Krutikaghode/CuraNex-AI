"""Report-aware assistant (retrieval-augmented generation)."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Patient
from app.db.session import get_db
from app.rag import service
from app.rag.llm import LLMProvider, LLMUnavailableError, get_llm
from app.schemas.assistant import AskRequest, AskResponse, AssistantStatus, IndexResponse
from app.services import patients as patient_service

router = APIRouter(tags=["assistant"])


def _patient(db: Session, patient_id: int) -> Patient:
    patient = patient_service.get_patient(db, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} was not found.")
    return patient


@router.get("/assistant/status", response_model=AssistantStatus)
def assistant_status(llm: LLMProvider = Depends(get_llm)) -> dict:
    return {
        "provider": llm.name,
        "chat_model": llm.chat_model,
        "embed_model": llm.embed_model,
        **llm.status(),
    }


@router.post("/patients/{patient_id}/assistant/index", response_model=IndexResponse)
def index_patient_reports(
    patient_id: int, db: Session = Depends(get_db), llm: LLMProvider = Depends(get_llm)
) -> dict:
    _patient(db, patient_id)
    try:
        reports = service.ensure_indexed(db, patient_id, llm)
    except LLMUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {"reports_indexed": len(reports)}


@router.post("/patients/{patient_id}/assistant/ask", response_model=AskResponse)
def ask_assistant(
    patient_id: int,
    payload: AskRequest,
    db: Session = Depends(get_db),
    llm: LLMProvider = Depends(get_llm),
) -> dict:
    patient = _patient(db, patient_id)
    try:
        answer = service.ask(db, patient, payload.question.strip(), llm)
    except LLMUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return asdict(answer)
