# Pharma Checker portal (React)

This folder builds the **splash, auth, and forgot-password** UI that FastAPI serves from **`http://localhost:8000`** (not a separate Node port in production).

## One-time build (required for auth UI on :8000)

From the **repository root**:

```bash
cd portal
npm install
npm run build
```

Then start the API from `fastapi/` (`uvicorn main:app --reload --port 8000`) and open **http://localhost:8000**.

## Auth API (same server)

The FastAPI app exposes:

- `POST /api/auth/signup`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`
- `POST /api/auth/forgot-password`, `POST /api/auth/reset-password`

User records live in **`fastapi/data/portal_users.json`**; reset tokens in **`fastapi/data/password_resets.json`** (demo: forgot-password returns a `reset_url` in JSON — no email is sent). Both paths are **gitignored**; create them locally as `{"users":[]}` / `{"resets":[]}` if missing (the server creates them on first write).

## Optional: standalone Node dev server

For React HMR while editing UI only:

```bash
cd portal
npm install
npm run dev
```

That runs **`portal/server/index.mjs`** on port **3000** (or the next free port in development) and proxies pharmacy APIs to FastAPI on **8000**. The integrated experience is still **uvicorn on 8000** after `npm run build`.
