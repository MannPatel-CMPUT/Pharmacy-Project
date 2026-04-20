from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from services.openfda_ingestion_service import sync_openfda_knowledge
from services.knowledge_ingestion_service import ingest_knowledge_upload
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


@router.post("/upload")
async def upload_knowledge_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    result = await ingest_knowledge_upload(file, db)
    return _merge_intake_refresh(db, result)
