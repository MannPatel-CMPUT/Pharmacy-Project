from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from services.openfda_ingestion_service import sync_openfda_knowledge
from services.knowledge_ingestion_service import ingest_knowledge_dataset

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/openfda-sync")
def openfda_sync(db: Session = Depends(get_db)):
    return sync_openfda_knowledge(db)


@router.post("/upload")
async def upload_knowledge_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()
    result = ingest_knowledge_dataset(file.filename, content, db)
    return result
