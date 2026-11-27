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
                                         +-- app/ml      diabetes risk model (XGBoost + SHAP)
                                         +-- app/reports PDF text extraction + Tesseract OCR
                                         +-- app/rag     chunking, embeddings, retrieval, cited answers
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
datasets/              training data (see datasets/README.md)
models/                trained model artifacts + metadata (committed)
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

## Diabetes risk model

`models/diabetes/` ships a trained XGBoost model (native JSON format, no pickle) and
`metadata.json` with its version, hyperparameters, dataset hash and held-out metrics
(currently ROC AUC 0.82, recall 0.83). To retrain:

```bash
python -m app.ml.train_diabetes   # grid search with 5-fold CV, ~10 s
```

Zeros in glucose, blood pressure, skin thickness, insulin and BMI are treated as missing.
Each prediction stores its inputs, model version and per-feature SHAP contributions, so
results are reproducible and explainable. Risk bands: low < 30% ≤ moderate < 60% ≤ high.
The training population (Pima women aged 21+) limits how far scores generalise.

| Endpoint | Purpose |
|---|---|
| `GET /models/diabetes` | Model metadata and metrics |
| `POST /patients/{id}/predictions/diabetes` | Score a patient and store the result |
| `GET /patients/{id}/predictions` | Prediction history |
| `GET /predictions/summary` | Risk distribution across active patients (latest per patient) |

## Medical reports

Upload PDF, PNG or JPEG (max 10 MB) per patient. The file type is checked from its bytes,
files are stored under random names in `CURANEX_DATA_DIR/reports/<patient_id>/`, and the
extracted text is saved with the report. PDF pages with a text layer are read directly with
PyMuPDF; pages without one (scans) and images are OCR'd with Tesseract. Local runs need the
`tesseract` binary (`brew install tesseract` / `apt install tesseract-ocr`); the Docker image
includes it.

| Endpoint | Purpose |
|---|---|
| `POST /patients/{id}/reports` | Upload (multipart `file`) and extract text |
| `GET /patients/{id}/reports` | List a patient's reports |
| `GET /reports/{id}` | Report metadata and extracted text |
| `GET /reports/{id}/file` | Download the original file |
| `GET /reports/count` | Number of successfully processed reports |

## AI assistant (RAG)

Ask questions about one patient's processed reports and get answers that cite the excerpts
they came from.

1. **Chunk** each report's text into ~900-character, page-aware chunks with overlap.
2. **Embed** chunks with `nomic-embed-text` via Ollama and store the vectors in the
   `report_chunks` table (JSON). Reports are indexed lazily on the first question, and
   re-indexed automatically if the embedding model changes.
3. **Retrieve** the top-k chunks for the patient by cosine similarity (numpy). Per-patient
   corpora are small, so a separate vector database adds operations cost without benefit.
4. **Generate** with `llama3.1:8b` via Ollama, using a system prompt that requires answers
   only from the excerpts, `[n]` citations, no diagnosis, and treats report text as untrusted
   data (prompt-injection guard).

Everything runs locally; no report text leaves the machine. Set `CURANEX_LLM_PROVIDER=fake`
for an offline demo with extractive answers (also used by the tests).

```bash
docker compose --profile llm up --build    # starts Ollama and pulls both models once
# or, without Docker: ollama serve && ollama pull llama3.1:8b && ollama pull nomic-embed-text

CURANEX_LLM_PROVIDER=ollama python -m app.rag.evaluate --verbose   # quality report
```

`app.rag.evaluate` runs 10 synthetic cases from `datasets/rag_eval/cases.json` (including an
injected instruction and an unanswerable question) and reports retrieval hit rate, answer
accuracy, citation rate and guardrail passes. Use it to tune `CURANEX_RAG_TOP_K` and
`CURANEX_RAG_MIN_SCORE` or to compare models.

| Endpoint | Purpose |
|---|---|
| `GET /assistant/status` | Provider, models, reachability, missing models |
| `POST /patients/{id}/assistant/index` | Index the patient's reports now |
| `POST /patients/{id}/assistant/ask` | `{"question": ...}` → answer + citations |

CI (GitHub Actions) runs lint, tests, a migration up/down check and a Docker build on every PR.

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Scope, README, disclaimer | Done |
| 1 | Foundation: single `app/` package, settings, SQLAlchemy + Alembic, Docker, CI, multipage UI | Done |
| 2 | Diabetes risk prediction (XGBoost on Pima dataset), stored predictions, model metrics on dashboard | Done |
| 3 | Medical report upload, PDF text extraction (PyMuPDF), OCR fallback (Tesseract) | Done |
| 4 | RAG assistant: chunking, Ollama embeddings, DB-backed retrieval, cited answers, eval set | Done |
| 5 | Health monitoring: vitals, trends, anomaly flags (statsmodels) | Planned |
| 6 | Auth: JWT, clinician role | Planned |
| 7 | LangGraph agent router (stretch) | Planned |
