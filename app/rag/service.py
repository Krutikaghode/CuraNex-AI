"""Index report text for retrieval and answer questions with citations."""

from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import MedicalReport, Patient, ReportChunk
from app.rag.chunking import chunk_text
from app.rag.llm import LLMProvider, LLMUnavailableError
from app.rag.prompts import SYSTEM_PROMPT, build_user_prompt

EMBED_BATCH = 32
NOT_FOUND = "I could not find this in the patient's reports."


@dataclass(frozen=True)
class Citation:
    number: int
    report_id: int
    filename: str
    page: int | None
    excerpt: str
    score: float


@dataclass(frozen=True)
class Answer:
    answer: str
    citations: list[Citation]
    provider: str
    chat_model: str
    embed_model: str
    reports_searched: int


def index_report(db: Session, report: MedicalReport, llm: LLMProvider) -> int:
    """(Re)build a report's chunks. Returns the number of chunks written."""
    settings = get_settings()
    db.execute(delete(ReportChunk).where(ReportChunk.report_id == report.id))
    chunks = chunk_text(report.text or "", settings.rag_chunk_chars, settings.rag_chunk_overlap)
    try:
        vectors: list[list[float]] = []
        for start in range(0, len(chunks), EMBED_BATCH):
            batch = chunks[start : start + EMBED_BATCH]
            vectors.extend(llm.embed([chunk.text for chunk in batch]))
    except LLMUnavailableError as error:
        db.rollback()
        report.index_error = str(error)
        db.commit()
        raise
    for chunk, vector in zip(chunks, vectors, strict=True):
        db.add(
            ReportChunk(
                report_id=report.id,
                patient_id=report.patient_id,
                chunk_index=chunk.index,
                page=chunk.page,
                text=chunk.text,
                embedding=vector,
            )
        )
    report.indexed_at = datetime.now(UTC)
    report.embedding_model = llm.embed_model
    report.index_error = None
    db.commit()
    return len(chunks)


def ensure_indexed(db: Session, patient_id: int, llm: LLMProvider) -> list[MedicalReport]:
    """Index any processed report not yet embedded with the current embedding model."""
    reports = list(
        db.scalars(
            select(MedicalReport).where(
                MedicalReport.patient_id == patient_id, MedicalReport.status == "processed"
            )
        )
    )
    for report in reports:
        if report.indexed_at is None or report.embedding_model != llm.embed_model:
            index_report(db, report, llm)
    return reports


def retrieve(
    db: Session, patient_id: int, question: str, llm: LLMProvider, top_k: int, min_score: float
) -> list[tuple[ReportChunk, float]]:
    rows = list(
        db.execute(
            select(ReportChunk)
            .join(MedicalReport, MedicalReport.id == ReportChunk.report_id)
            .where(
                ReportChunk.patient_id == patient_id,
                MedicalReport.embedding_model == llm.embed_model,
            )
        ).scalars()
    )
    if not rows:
        return []
    matrix = np.asarray([row.embedding for row in rows], dtype=float)
    query = np.asarray(llm.embed([question])[0], dtype=float)
    norms = np.linalg.norm(matrix, axis=1) * (np.linalg.norm(query) or 1.0)
    scores = matrix @ query / np.where(norms == 0, 1.0, norms)
    order = np.argsort(-scores)[:top_k]
    return [(rows[i], float(scores[i])) for i in order if scores[i] >= min_score]


def ask(db: Session, patient: Patient, question: str, llm: LLMProvider) -> Answer:
    settings = get_settings()
    reports = ensure_indexed(db, patient.id, llm)
    hits = retrieve(db, patient.id, question, llm, settings.rag_top_k, settings.rag_min_score)

    citations = [
        Citation(
            number=n,
            report_id=chunk.report_id,
            filename=chunk.report.filename,
            page=chunk.page,
            excerpt=chunk.text,
            score=round(score, 4),
        )
        for n, (chunk, score) in enumerate(hits, 1)
    ]
    if not citations:
        text = NOT_FOUND if reports else "This patient has no processed reports yet."
    else:
        excerpts = [
            (c.number, f"({c.filename}" + (f", page {c.page})" if c.page else ")"), c.excerpt)
            for c in citations
        ]
        text = llm.chat(SYSTEM_PROMPT, build_user_prompt(question, excerpts))
    return Answer(
        answer=text,
        citations=citations,
        provider=llm.name,
        chat_model=llm.chat_model,
        embed_model=llm.embed_model,
        reports_searched=len(reports),
    )
