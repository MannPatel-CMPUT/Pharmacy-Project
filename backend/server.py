"""Supervisor entry point — re-exports the FastAPI app from /app/fastapi/main.py."""
from __future__ import annotations

import sys
from pathlib import Path

# Make the project's fastapi/ package importable (it contains main.py, routers/, etc.)
_FASTAPI_DIR = Path(__file__).resolve().parent.parent / "fastapi"
if str(_FASTAPI_DIR) not in sys.path:
    sys.path.insert(0, str(_FASTAPI_DIR))

# Ensure runtime cwd-relative resources (sqlite db, json data) resolve correctly.
import os
os.chdir(str(_FASTAPI_DIR.parent))

from main import app  # noqa: E402,F401  (re-export for uvicorn server:app)
