# CuraNex AI

An educational healthcare decision-support prototype: patient management, ML-based disease
risk prediction, medical report analysis with a report-aware AI assistant, and health
monitoring.

> **Disclaimer.** CuraNex AI is a portfolio/academic project, not a medical device or
> diagnostic system. Use synthetic or public de-identified data only. Never enter real
> patient information.

## Architecture

```
Streamlit UI (frontend/)  --HTTP-->  FastAPI (app/)  -->  SQLAlchemy  -->  SQLite (dev) / Postgres (compose)
                                         |
                                         +-- app/ml      diabetes risk model (Phase 2)
                                         +-- app/rag     report ingestion + retrieval (Phases 3-4)
                                         +-- app/agents  LangGraph router (Phase 7, stretch)
                                         +-- Ollama      local LLM, optional compose profile
```

```
app/
  main.py              FastAPI app
  core/config.py       settings (env vars prefixed CURANEX_)
  db/                  engine/session, ORM models
  schemas/             Pydantic request/response models
  services/            business logic, no HTTP
  api/routes/          HTTP endpoints
migrations/            Alembic migrations
frontend/
  app.py               Streamlit entrypoint and navigation
  views/               one file per page
docker/                Dockerfiles for api and ui
tests/                 pytest suite
```

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # optional; defaults use SQLite in ./data

alembic upgrade head            # create/upgrade the database
uvicorn app.main:app --reload   # API on http://127.0.0.1:8000 (docs at /docs)

cd frontend && streamlit run app.py   # UI on http://localhost:8501
```

## Run with Docker

```bash
docker compose up --build                 # postgres + api + ui
docker compose --profile llm up --build   # also starts Ollama (needs ~8 GB RAM)
```

The API container runs `alembic upgrade head` on start. UI: http://localhost:8501,
API: http://localhost:8000/docs.

## Development

```bash
pytest -q
ruff check . && ruff format --check .
alembic revision --autogenerate -m "describe change"   # after changing app/db/models.py
```

CI (GitHub Actions) runs lint, tests, a migration up/down check and a Docker build on every PR.

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Scope, README, disclaimer | Done |
| 1 | Foundation: single `app/` package, settings, SQLAlchemy + Alembic, Docker, CI, multipage UI | Done |
| 2 | Diabetes risk prediction (XGBoost on Pima dataset), stored predictions, model metrics on dashboard | Planned |
| 3 | Medical report upload, PDF text extraction (PyMuPDF), OCR fallback (Tesseract) | Planned |
| 4 | RAG assistant: chunking, embeddings, Chroma, Ollama, cited answers, eval set | Planned |
| 5 | Health monitoring: vitals, trends, anomaly flags (statsmodels) | Planned |
| 6 | Auth: JWT, clinician role | Planned |
| 7 | LangGraph agent router (stretch) | Planned |
