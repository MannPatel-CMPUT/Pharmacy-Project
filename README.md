# 💊 PairWise Rx — Pharmacy workflow

A FastAPI + SQLite workflow system for pharmacy intake processing with deterministic drug interaction detection (from your `db_drug_interactions.csv`), template-based counseling text, and optional manual dataset ingestion for tests.

> **Disclaimer:** Educational prototype only. Not for diagnosis or prescribing.

---

## Features

- 7-stage deterministic workflow: `new → triage → waiting_info → ready_to_fill → filled → dispensed → completed`
- Deterministic interaction engine (no LLM detection/severity assignment)
- Drug interaction data loaded at server startup from **`DRUG_INTERACTIONS_CSV`** (or `fastapi/data/db_drug_interactions.csv`), plus a merge from **`fastapi/data/drug_interactions.json`** for common pairs the bulk CSV may omit (e.g. warfarin + aspirin).
- Counseling generation: deterministic template output (no LLM)
- Frontend dashboard (vanilla HTML/CSS/JS):
  - intake creation
  - interaction/result visualization
  - workflow stage labels and optional browser pickup alerts

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

### 3) Build PairWise Rx shell (splash, login, sign up)

```bash
cd portal
npm install
npm run build
cd ..
```

### 4) Start backend (serves API + portal + `/workspace` dashboard on port 8000)

```bash
cd fastapi
uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000** — sign in or sign up, then you are sent to **`/workspace`** for the pharmacy dashboard.

### 5) Optional: legacy second origin

If you still serve `frontend/` from another port (e.g. 8080), keep that origin in **`FRONTEND_URL`** in `.env`.

---

## Environment Variables

See `.env.example`.

Key values:

- `DATABASE_URL` (default: `sqlite:///./pharmacy.db`)
- `FRONTEND_URL` — comma-separated CORS origins; default in code includes `http://localhost:8000` and `http://localhost:8080`
- `JWT_SECRET` — signing key for PairWise Rx auth cookies (set in production)
- `DRUG_INTERACTIONS_CSV` — absolute path to `db_drug_interactions.csv` (Drug 1, Drug 2, Interaction Description). Loaded once on startup if the DB has no rows from that source yet.
- `DDI_CSV_COMMIT_EVERY` (optional) — batch size during CSV ingest (default `2000`).

`GET /config/status` reports `counseling_engine: template` and `llm_enabled: false`.

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
curl -X POST http://localhost:8000/intakes/1/check-interactions
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
- Bulk interaction pairs from `DRUG_INTERACTIONS_CSV` at startup
- Template-based counseling (deterministic)
- Automated test coverage for major backend paths

### Not yet production-level

- No auth/role-based access control
- No migration framework (uses lightweight SQLite backfill only)
- Interaction text comes from your CSV; no clinical adjudication layer
- No background job queue for long CSV loads (first startup can take time)
- No observability stack (metrics/traces/alerts)
- No hardened input sanitization/audit/PII compliance workflow
- Limited frontend UX polish and accessibility checks

