from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from services.openfda_ingestion_service import sync_openfda_knowledge
from services import intake_service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _merge_intake_refresh(db, result: dict) -> dict:
    if result.get("fatal") or result.get("error"):
        return result
    snap = intake_service.refresh_all_intake_interaction_snapshots(db)
    result["intakes_updated"] = snap["intakes_updated"]
    return result


@router.post("/openfda-sync")
def openfda_sync(db: Session = Depends(get_db)):
    result = sync_openfda_knowledge(db)
    return _merge_intake_refresh(db, result)
