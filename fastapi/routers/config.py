from fastapi import APIRouter

from services.ollama_service import check_ollama_status

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/status")
def config_status():
    return check_ollama_status()
