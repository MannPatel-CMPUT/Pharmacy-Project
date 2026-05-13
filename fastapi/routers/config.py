from fastapi import APIRouter

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/status")
def config_status():
    """Minimal config surface; LLM counseling is not used."""
    return {
        "counseling_engine": "template",
        "llm_enabled": False,
    }
