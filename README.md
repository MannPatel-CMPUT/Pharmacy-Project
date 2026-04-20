# 💊 Pharmacy Workflow Automation System

A FastAPI + SQLite workflow system for pharmacy intake processing with deterministic drug interaction detection, optional Ollama-based counseling formatting, and knowledge ingestion pipelines.

> **Disclaimer:** Educational prototype only. Not for diagnosis or prescribing.

---

## Features

- 7-stage deterministic workflow: `new → triage → waiting_info → ready_to_fill → filled → dispensed → completed`
- Deterministic interaction engine (no LLM detection/severity assignment)
- Rule/data ingestion from:
  - seed JSON (`fastapi/data/drug_interactions.json`)
  - openFDA sync endpoint
  - manual CSV/JSON dataset upload endpoint
- Counseling generation pipeline:
  - tries Ollama for structured counseling output
  - falls back to template-based deterministic counseling if Ollama fails
- Frontend dashboard (vanilla HTML/CSS/JS):
  - intake creation
  - interaction/result visualization
  - openFDA sync
  - dataset upload

---

## Quick Setup

### 1) Clone and install

```bash
git clone <repo-url>
cd Pharmacy-Project
pip install -r requirements.txt
```

### 2) Configure environment

```bash
cp .env.example .env
```

Default `.env` values work locally with SQLite.

### 3) Start backend

```bash
cd fastapi
uvicorn main:app --reload --port 8000
```

### 4) Open frontend

Serve `frontend/index.html` over HTTP (or use app root if backend serves static):

```bash
cd frontend
python -m http.server 8080
```

---

## Environment Variables

See `.env.example`.

Key values:

- `DATABASE_URL` (default: `sqlite:///./pharmacy.db`)
- `FRONTEND_URL` (default: `http://localhost:8080`)
- `OLLAMA_BASE_URL` (default: `http://localhost:11434`)
- `OLLAMA_MODEL` (default: `llama3`)

---

## openFDA Usage

### Trigger sync

```bash
curl -X POST http://localhost:8000/knowledge/openfda-sync
```

Example response:

```json
{
  "total_fetched": 25,
  "parsed": 16,
  "inserted": 9,
  "failed": 3
}
```

---

## Dataset Upload Usage

Upload CSV/JSON containing fields:

- `drug_a`
- `drug_b`
- `severity`
- `clinical_effect`
- `mechanism`
- `monitoring`

### CSV upload

```bash
curl -X POST http://localhost:8000/knowledge/upload \
  -F "file=@sample_data/interaction_dataset_sample.csv"
```

---

## Ollama Setup

1. Install Ollama locally: https://ollama.com
2. Pull model (example):

```bash
ollama pull llama3
```

3. Ensure `.env` values:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

4. Check app-visible status:

```bash
curl http://localhost:8000/config/status
```

If Ollama is down/unreachable, counseling automatically falls back to template mode.

---

## Example API Calls

### Health

```bash
curl http://localhost:8000/health
```

### Create intake

```bash
curl -X POST http://localhost:8000/intakes \
  -H "Content-Type: application/json" \
  -d '{
    "patient_name": "Jane Doe",
    "patient_age": 67,
    "medications": "warfarin",
    "current_medications": "aspirin"
  }'
```

### Re-check interactions

```bash
curl http://localhost:8000/intakes/1/check-interactions
```

---

## Testing

```bash
pytest -q
```

---

## MVP vs Production-Level

### Current MVP strengths

- Deterministic interaction detection/prioritization and workflow transitions
- Basic ingestion from openFDA and file upload
- Template fallback when Ollama fails
- Automated test coverage for major backend paths

### Not yet production-level

- No auth/role-based access control
- No migration framework (uses lightweight SQLite backfill only)
- Limited interaction ontology and heuristic parsing for openFDA text
- No background job queue for long-running syncs/uploads
- No observability stack (metrics/traces/alerts)
- No hardened input sanitization/audit/PII compliance workflow
- Limited frontend UX polish and accessibility checks

