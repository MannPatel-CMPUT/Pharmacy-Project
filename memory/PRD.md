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
- 34/34 backend pytest tests pass.
- testing_agent_v3 iteration 1: 100% on critical flows; 0 critical bugs; 2 minor follow-ups addressed (forgot-password TLD validator relaxed; search-view de-duplicated).

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
