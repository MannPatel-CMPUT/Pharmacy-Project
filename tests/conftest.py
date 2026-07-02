import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fastapi"))

# In-memory tests must not ingest a developer's full DDII CSV (main.py loads .env with override=False).
os.environ["DRUG_INTERACTIONS_CSV"] = ""
os.environ.pop("DDI_CSV_FORCE_RELOAD", None)

# Legacy tests instantiate ``TestClient(app)`` at module scope, which does not
# trigger FastAPI's ``lifespan`` startup hook (that only fires inside a
# ``with TestClient(app):`` block). Explicitly initialise the schema here so
# tables added post-hoc (``portal_users`` in Feb 2026, etc.) exist before any
# request-driven query hits the DB.
from database import init_db_schema  # noqa: E402
init_db_schema()
