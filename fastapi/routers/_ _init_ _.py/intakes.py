from schemas.intake_actions import StatusUpdate, AssignUser
from fastapi import APIRouter, HTTPException
from schemas.intake import IntakeCreate, IntakeOut
from services import intake_service

router = APIRouter(prefix="/intakes", tags=["intakes"])


@router.post("", response_model=IntakeOut)
def create_intake(payload: IntakeCreate):
    return intake_service.create_intake(payload)


@router.get("", response_model=list[IntakeOut])
def list_intakes():
    return intake_service.list_intakes()


@router.get("/{intake_id}", response_model=IntakeOut)
def get_intake(intake_id: int):
    intake = intake_service.get_intake_by_id(intake_id)
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return intake

@router.post("/{intake_id}/status", response_model=IntakeOut)
def change_status(intake_id: int, payload: StatusUpdate):
    try:
        intake = intake_service.update_status(intake_id, payload.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return intake


@router.post("/{intake_id}/assign", response_model=IntakeOut)
def assign_intake(intake_id: int, payload: AssignUser):
    intake = intake_service.assign_intake(intake_id, payload.user)
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return intake