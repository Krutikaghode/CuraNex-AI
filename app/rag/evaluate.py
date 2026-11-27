"""Offline evaluation of retrieval and answers against synthetic cases.

    CURANEX_LLM_PROVIDER=ollama python -m app.rag.evaluate

Uses a throwaway SQLite database. Reports:
  retrieval_hit  - every expected string appears in at least one retrieved chunk
  answer_hit     - every expected string appears in the answer
  cited          - the answer contains at least one [n] citation (when something was expected)
  guardrails     - "must_not" strings are absent; unanswerable questions say "could not find"
"""

import argparse
import json
import re
import tempfile
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db import models
from app.db.base import Base
from app.db.session import build_engine
from app.rag import service
from app.rag.llm import get_llm

CASES = Path(__file__).resolve().parents[2] / "datasets" / "rag_eval" / "cases.json"


def run(cases_path: Path = CASES) -> dict:
    spec = json.loads(cases_path.read_text())
    llm = get_llm()
    with tempfile.TemporaryDirectory() as tmp:
        engine = build_engine(f"sqlite:///{tmp}/eval.db")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine, expire_on_commit=False)()
        patient = models.Patient(full_name="Eval Patient", age=52, gender="female")
        db.add(patient)
        db.commit()
        for item in spec["reports"]:
            db.add(
                models.MedicalReport(
                    patient_id=patient.id,
                    filename=item["filename"],
                    content_type="application/pdf",
                    size_bytes=len(item["text"]),
                    sha256="eval",
                    storage_path="eval",
                    status="processed",
                    extraction_method="text",
                    page_count=item["text"].count("--- Page"),
                    text=item["text"],
                )
            )
        db.commit()

        rows, totals = [], {"retrieval_hit": 0, "answer_hit": 0, "cited": 0, "guardrails": 0}
        counted = {"retrieval_hit": 0, "answer_hit": 0, "cited": 0, "guardrails": 0}
        for case in spec["cases"]:
            answer = service.ask(db, patient, case["question"], llm)
            retrieved = "\n".join(c.excerpt for c in answer.citations)
            row = {"question": case["question"], "answer": answer.answer}
            if case["expect"]:
                row["retrieval_hit"] = all(e in retrieved for e in case["expect"])
                row["answer_hit"] = all(e.lower() in answer.answer.lower() for e in case["expect"])
                row["cited"] = bool(re.search(r"\[\d+\]", answer.answer))
            if case.get("must_not") or case.get("expect_not_found"):
                ok = all(m.lower() not in answer.answer.lower() for m in case.get("must_not", []))
                if case.get("expect_not_found"):
                    ok = ok and "could not find" in answer.answer.lower()
                row["guardrails"] = ok
            for key in totals:
                if key in row:
                    counted[key] += 1
                    totals[key] += int(row[key])
            rows.append(row)
        db.close()
        engine.dispose()

    summary = {key: f"{totals[key]}/{counted[key]}" for key in totals if counted[key]} | {
        "provider": llm.name,
        "chat_model": llm.chat_model,
        "embed_model": llm.embed_model,
    }
    return {"summary": summary, "cases": rows, "top_k": get_settings().rag_top_k}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    result = run(args.cases)
    print(json.dumps(result if args.verbose else result["summary"], indent=2))


if __name__ == "__main__":
    main()
