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
- `OLLAMA_TIMEOUT_SECONDS` (optional, default `30`) — HTTP timeout for Ollama `/api/generate`
- `OPENFDA_API_KEY` (optional) — [openFDA API key](https://open.fda.gov/apis/authentication/) to reduce rate-limit failures
- `OPENFDA_TIMEOUT_SECONDS` (optional, default `30`) — HTTP timeout for openFDA label fetch
- `OPENFDA_ALLOW_MEDIUM` (optional, default `true`) — also persist **medium-confidence** co-mention pairs from SPL text as `DrugInteraction` rows with `source=openfda_medium`

**Render / cloud:** `OLLAMA_BASE_URL=http://localhost:11434` points at the **container**, not your laptop. Ollama will be unreachable unless you run Ollama on a reachable host (VPS, tunnel) and set `OLLAMA_BASE_URL` to that URL. Counseling then falls back to the template engine (see `counseling_source` on `GET /intakes/{id}/check-interactions`).

---

## openFDA Usage

### Trigger sync

```bash
curl -X POST http://localhost:8000/knowledge/openfda-sync
```

Example response (counts only; failures include `error` and HTTP details when the fetch fails):

```json
{
  "total_fetched": 25,
  "parsed": 16,
  "inserted": 9,
  "skipped": 40,
  "failed": 0,
  "skip_reason_counts": {
    "low_confidence": 30,
    "existing_pair": 10
  },
  "intakes_updated": 3
}
```

Successful `openfda-sync` and `/knowledge/upload` responses include **`intakes_updated`**: the server re-runs interaction detection for **every intake** so list cards pick up new `DrugInteraction` rows without manual **Re-check**.

When `inserted` is `0` but labels were fetched, the API may include a `hint` (e.g. duplicates, pattern misses, or `OPENFDA_ALLOW_MEDIUM=false` skipping co-mentions).

---

## Dataset Upload Usage

### openFDA label JSON (bulk download from open.fda.gov)

You can upload the same JSON shape the API returns: an object with **`results`** (array of SPL label objects), optionally with **`meta`**. Example: `drug-label-0001-of-0013.json` from the openFDA site. The app ingests it the same way as **Sync openFDA** and returns `format: "openfda_label_json"` plus the usual `total_fetched` / `parsed` / `inserted` / `skipped` / `failed` fields.

### Flat dataset (CSV or curated JSON)

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

