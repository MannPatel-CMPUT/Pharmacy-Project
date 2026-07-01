import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

_fastapi_dir = Path(__file__).resolve().parent
_repo_root = _fastapi_dir.parent
try:
    from dotenv import load_dotenv

    load_dotenv(_repo_root / ".env", override=False)
    load_dotenv(_fastapi_dir / ".env", override=False)
except ImportError:
    pass

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from database import init_db_interaction_sources, init_db_schema
from routers.auth import router as auth_router
from routers.config import router as config_router
from routers.intakes import router as intakes_router
from routers.google_auth import router as google_auth_router
from services import auth_service
import os


_REPO_ROOT = _repo_root
_FRONTEND = _REPO_ROOT / "frontend"
# Optional: absolute path to portal Vite output (default: repo/portal/client/dist)
_PORTAL_DIST = Path(
    os.getenv("PORTAL_DIST", str(_REPO_ROOT / "portal" / "client" / "dist"))
).resolve()
_PORTAL_INDEX = _PORTAL_DIST / "index.html"
_PORTAL_ASSETS = _PORTAL_DIST / "assets"
_PORTAL_OK = _PORTAL_INDEX.is_file() and _PORTAL_ASSETS.is_dir()

_PORTAL_SHELL_PREFIXES = frozenset(
    {"login", "signup", "forgot-password", "reset-password"}
)

_PORTAL_SETUP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Build PairWise Rx UI</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 520px; margin: 48px auto; padding: 0 20px; line-height: 1.5; color: #1e293b; }
    code { background: #f1f5f9; padding: 2px 8px; border-radius: 6px; display: block; margin: 12px 0; white-space: pre-wrap; }
    a { color: #2563eb; }
  </style>
</head>
<body>
  <h1>PairWise Rx UI is not built yet</h1>
  <p>The login / sign-up screens are a React app that must be compiled into <code>portal/client/dist</code> before this server can show them on port 8000.</p>
  <p><strong>From your project root</strong> (the folder that contains <code>portal</code> and <code>fastapi</code>), run:</p>
  <code>cd portal
npm install
npm run build</code>
  <p>Then <strong>restart</strong> <code>uvicorn</code> and open <a href="/">http://localhost:8000/</a> again.</p>
  <p>If you only need the pharmacy dashboard without the login shell, use <a href="/pharmacy">/pharmacy</a>.</p>
</body>
</html>"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db_schema()
        print("✓ Database initialized (schema)")
    except Exception as e:
        print(f"⚠ Database initialization warning: {e}")

    async def _load_interactions_bg() -> None:
        try:
            await asyncio.to_thread(init_db_interaction_sources)
            print("✓ Drug interaction data load finished (CSV / seed)")
        except Exception as e:
            print(f"⚠ Drug interaction load failed: {e}")

    interaction_task = asyncio.create_task(_load_interactions_bg())

    if _PORTAL_OK:
        print(f"✓ PairWise Rx portal UI enabled ({_PORTAL_DIST})")
    else:
        print(f"⚠ Portal UI missing or incomplete — expected {_PORTAL_INDEX}")
        if _PORTAL_INDEX.is_file() and not _PORTAL_ASSETS.is_dir():
            print("  (index.html exists but assets/ is missing — run a full npm run build in portal/)")
        print("  Run: cd portal && npm install && npm run build")
    yield
    try:
        await interaction_task
    except Exception:
        pass


app = FastAPI(
    title="PairWise Rx API",
    description="Backend API for PairWise Rx pharmacy workflow",
    version="1.0.0",
    lifespan=lifespan,
)

# Add session middleware for OAuth (required by authlib)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("JWT_SECRET", "rxflow-dev-only-shared-secret"),
    max_age=7 * 24 * 60 * 60,  # 7 days
)

_default_origins = "http://localhost:8000,http://localhost:8080"
_origins = [o.strip() for o in os.getenv("FRONTEND_URL", _default_origins).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_HTML_NO_CACHE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
}


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "PairWise Rx API is running"}


app.include_router(auth_router)
app.include_router(google_auth_router)
app.include_router(intakes_router)
app.include_router(config_router)


def _pharmacy_index() -> Path:
    return _FRONTEND / "index.html"


def _portal_index_response() -> FileResponse:
    return FileResponse(str(_PORTAL_INDEX), headers=_HTML_NO_CACHE)


def _spa_path_blocked(path: str) -> bool:
    """Do not serve the React SPA shell for API-like paths (defensive)."""
    if not path or path in (".",):
        return True
    first = path.split("/", 1)[0].lower()
    return first in (
        "intakes",
        "api",
        "health",
        "config",
        "static",
        "assets",
        "workspace",
        "pharmacy",
    )


if _FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(_FRONTEND)), name="static")

if _PORTAL_OK:
    app.mount("/assets", StaticFiles(directory=str(_PORTAL_ASSETS)), name="portal_assets")

    @app.get("/workspace")
    async def workspace(request: Request):
        if not auth_service.verify_session_cookie(request):
            return RedirectResponse(url="/login?next=/workspace", status_code=302)
        if not _pharmacy_index().is_file():
            raise HTTPException(status_code=500, detail="Pharmacy UI missing.")
        return FileResponse(str(_pharmacy_index()), headers=_HTML_NO_CACHE)

    @app.get("/")
    async def portal_root():
        return _portal_index_response()

    @app.get("/{path:path}")
    async def portal_spa(path: str):
        if _spa_path_blocked(path):
            raise HTTPException(status_code=404, detail="Not Found")
        file_path = _FRONTEND / path
        if (
            file_path.is_file()
            and str(file_path.resolve()).startswith(str(_FRONTEND.resolve()))
        ):
            return FileResponse(str(file_path), headers=_HTML_NO_CACHE)
        return _portal_index_response()

else:

    @app.get("/pharmacy")
    async def pharmacy_dashboard():
        if not _pharmacy_index().is_file():
            raise HTTPException(status_code=500, detail="Pharmacy UI missing.")
        return FileResponse(str(_pharmacy_index()), headers=_HTML_NO_CACHE)

    @app.get("/")
    async def read_root():
        return HTMLResponse(_PORTAL_SETUP_HTML)

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        first = path.split("/", 1)[0].lower()
        if first in _PORTAL_SHELL_PREFIXES:
            return HTMLResponse(_PORTAL_SETUP_HTML)
        file_path = _FRONTEND / path
        if file_path.is_file() and str(file_path.resolve()).startswith(str(_FRONTEND.resolve())):
            return FileResponse(str(file_path), headers=_HTML_NO_CACHE)
        return FileResponse(str(_pharmacy_index()), headers=_HTML_NO_CACHE)
