"""Single entry point that routes a question to reports, risk, vitals or an overview."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.graph import run_agent
from app.db.session import get_db
from app.rag.llm import LLMProvider, LLMUnavailableError, get_llm
from app.schemas.agent import AgentRequest, AgentResponse
from app.services import patients as patient_service

router = APIRouter(tags=["agent"])


@router.post("/patients/{patient_id}/agent/ask", response_model=AgentResponse)
def ask_agent(
    patient_id: int,
    payload: AgentRequest,
    db: Session = Depends(get_db),
    llm: LLMProvider = Depends(get_llm),
) -> dict:
    patient = patient_service.get_patient(db, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} was not found.")
    try:
        state = run_agent(db, patient, payload.question.strip(), llm)
    except LLMUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {
        "intent": state["intent"],
        "router": state["router"],
        "answer": state["answer"],
        "sections": state.get("sections", []),
        "citations": state.get("citations", []),
        "steps": state["steps"],
    }
