import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fastapi"))

# In-memory tests must not ingest a developer's full DDII CSV (main.py loads .env with override=False).
os.environ["DRUG_INTERACTIONS_CSV"] = ""
os.environ.pop("DDI_CSV_FORCE_RELOAD", None)
