import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fastapi"))

# Avoid live openFDA HTTP on every intake interaction test (enable per-test if needed).
os.environ.setdefault("OPENFDA_ENRICH_ON_INTAKE", "false")
