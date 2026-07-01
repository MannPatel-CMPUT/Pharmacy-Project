# RxFlow — Product Requirements Document

## Original problem statement
> "can you make it more professional, look like an actual thing, keep logic same, ask for any logic changes necessary for improvement"

Existing app: **Pharmacy Workflow Automation** — FastAPI + vanilla HTML dashboard + React/Vite auth portal. Brand restated as **RxFlow**.

## Architecture
- **Auth portal** (`/app/portal/`) — React 18 + Vite + TypeScript. Node/Express server on `:3000` (`yarn start` via supervisor `frontend`). Serves Splash/Login/Signup/Forgot/Reset and `/workspace` (cookie-protected). Proxies `/intakes /health /config /api/auth/forgot-password /api/auth/reset-password` to FastAPI on `:8001`.
- **API** (`/app/fastapi/`) — FastAPI on `:8001` (via `/app/backend/server.py` shim under supervisor `backend`). SQLite at `/app/pharmacy.db`. Loads `.env` via python-dotenv before importing the app.
- **Workspace dashboard** (`/app/frontend/index.html`) — single static HTML+CSS+JS file served by Node `/workspace`. Uses Lucide via CDN, IBM Plex Sans / Outfit / IBM Plex Mono via Google Fonts.
- **Shared auth** — both servers sign JWT cookies with the same `JWT_SECRET=rxflow-dev-only-shared-secret`; FastAPI uses `options={"verify_sub": False}` to accept Node-issued tokens (Node signs `sub` as number).

## User personas
- **Staff pharmacist** — creates intakes, screens interactions, advances Rx through workflow, dispenses, counsels patients.
- **Pharmacy tech** — assists with triage and data entry, assigned to intakes.

## Core requirements (static)
1. Auth: signup, login, logout, forgot-password (demo returns link), reset-password.
2. Intake CRUD with 7-stage workflow (`new → triage → waiting_info → ready_to_fill → filled → dispensed → completed`).
3. Deterministic drug interaction detection (severity tags + recommendations).
4. Allergy + lifestyle warning derivation from patient context.
5. Template-based counseling generation, editable.
6. Patient search by name.
7. Stats summary (counts by status, dispensed, ready-for-pickup).
8. Pickup notification (desktop / copy / SMS / email).
9. Audit trail of status transitions (timestamp + actor).

## What's been implemented (May 13, 2026)
- **Brand & UI redesign** — single unified RxFlow design system, dual-mode (dark glass for auth, light Swiss clinical for workspace).
- **Auth portal** — 5 redesigned pages (Splash, Login, Signup, Forgot, Reset) with Lucide icons, password-eye toggle, animated splash, IBM Plex/Outfit typography, glass cards with grid scaffold backdrop.
- **Workspace dashboard** — full rewrite of `/app/frontend/index.html`:
  - Sticky header with RxFlow wordmark, global debounced search, user chip + logout
  - 5 stat tiles with Lucide icons + skeleton loader
  - Quick filter chips (replaces dropdown) with live counts per status
  - Severity-sorted interaction list (Contraindicated → Major → Moderate → Minor → Unknown)
  - Workflow stepper per card with active/done/pickup tinting
  - Audit trail section on every card fetching `/intakes/{id}/history`
  - Pickup callout panel with Desktop/Copy/SMS/Email actions
  - Counseling modal restyled
  - Toast notification system for all actions (success/error/warning)
  - Empty / loading / error states properly designed
- **Backend logic improvements** (logic preserved, additions only):
  - `_sort_interactions_by_severity()` applied at create, recheck, evaluate.
  - `update_status()` and `dispense_medication()` capture `changed_by` from the session cookie.
  - `decode_token()` relaxes `verify_sub` to accept Node-signed tokens.
  - Server-shim loads `/app/backend/.env` before app import (python-dotenv).
  - `_LooseEmail` validator accepts RFC 2606 reserved TLDs (`.test`, `.example`, …) so demo accounts work.
  - `/api/auth/forgot-password` builds reset_url from `X-Forwarded-Host` so it points at the public preview origin.
- **Portal infra fixes**:
  - `vite.config.ts` → `allowedHosts: true` (preview hostnames).
  - `index.mjs` → proxy registered BEFORE `express.json()` so POST bodies stream through.
  - `/api/auth/forgot-password` and `/reset-password` proxied to FastAPI.
- **Supervisor scaffolding**:
  - `/app/backend/server.py` shim → imports `main:app` from `/app/fastapi`.
  - `/app/frontend/package.json` shim → launches Node portal with shared secret.

## Testing status
- 54/54 backend pytest tests pass (including 18 new ddi_severity_classifier tests).
- testing_agent_v3 iteration 1: 100% on critical flows; 0 critical bugs; 2 minor follow-ups addressed (forgot-password TLD validator relaxed; search-view de-duplicated).

## DDII risk classifier rebuild (Jan 2026)
- Problem: every drug pair in `fastapi/data/db_drug_interactions.csv` was labelled either `moderate` (184,616) or `major` (6,925) — clinically high-risk patterns (QT prolongation, serotonergic, anticoagulant, hypoglycemic, hypokalemic, AV block, arrhythmogenic) all bucketed as `moderate`, and protective pairs ("may decrease the cardiotoxic activities of …") were also `moderate`.
- Fix in `fastapi/services/ddi_severity_classifier.py`: keyword rules now recognise (a) high-risk activity increase → **major**, (b) "decrease the <toxic/sedative/CNS depressant/anticoagulant/serotonergic/…> activities" → **minor** (protective), (c) explicit "contraindicated / should not be used / must not" → **contraindicated**, (d) PK shifts (metabolism / serum concentration / efficacy) → **moderate**.
- New distribution: `major 22,400 / moderate 167,302 / minor 1,839`. CSV regenerated with `scripts/add_ddii_risk_severity_column.py`; DB re-ingested at startup (manifest fingerprint changed).

## Postgres migration + DDII CSV manifest fix (Feb 2026)
- App migrated SQLite → PostgreSQL (Render). Added `psycopg2-binary`, `authlib`, `itsdangerous` to `requirements.txt`.
- Custom Google OAuth added (`/app/fastapi/routers/google_auth.py` + `Login.tsx`).
- **P0 bug fixed**: `sqlalchemy.orm.exc.StaleDataError` during `db_drug_interactions.csv` ingestion on Postgres deploy.
  - **Root cause**: `_load_ddii_csv_if_configured()` in `/app/fastapi/database.py` used a `db.get()` → `db.query(...).delete()` → `db.merge()` pattern. After delete, the previously-loaded `DdiCsvIngestManifest` row remained in the session identity map as `persistent`; `merge()` then emitted an UPDATE against a row that no longer existed → 0 rows affected → `StaleDataError` (Postgres surfaces this; SQLite silently accepted it).
  - **Fix**: Replaced delete-then-merge with an in-place update (or `db.add()` when the manifest row is absent). Same pattern applied to both the "start of ingest" (ingest_complete=0) and "end of ingest" (ingest_complete=1) writes.
  - **Verified locally**: All three code paths pass — fresh INSERT (191,135 pairs loaded), forced UPDATE-in-place (previously crashed), and no-op SKIP on unchanged CSV.
- **New endpoint**: `GET /api/admin/ddi-stats` (cookie-authenticated) — returns `{drug_interactions_total, by_source, by_severity, csv_manifest}`. Verified end-to-end: 191,135 CSV + 4 seed_json rows, manifest `ingest_complete=true`. Unauthenticated → 401. Portal Node proxy updated in `/app/portal/server/index.mjs` to forward `/api/admin/*` to FastAPI.

## Prioritized backlog / Future
- **P1**: Add `data-testid='audit-{id}'` was added in iteration 1 review; harden CSV ingest path for very large interaction datasets (current code already batches).
- **P2**: Replace the inline emoji in counseling template output (backend `template_service`) with neutral text or icon tokens.
- **P2**: Split `/app/frontend/index.html` (~1900 LOC) into ES modules / component fragments (`renderIntakeCard`, `renderStats`, `renderInteractions`, `toast`, etc.) once tooling allows.
- **P2**: Add a real audit-trail page (full timeline view) per intake.
- **P3**: Multi-user concurrency awareness (show who is editing).
- **P3**: Export intake (PDF) for patient handout.
- **P3**: Real email/SMS integration for pickup notifications (SendGrid + Twilio) — currently uses native `mailto:` / `sms:` and browser Notifications API.

## Next tasks if continuing
1. Decide if the workspace dashboard should also move to React (for component reuse with the portal) or stay single-file (current preference).
2. Consider seeding more demo intakes covering all 7 workflow stages for richer demo.
3. Consider exposing the user filter (assigned_to) as additional chips alongside status chips.
