from schemas.intake_actions import StatusUpdate, AssignUser
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from schemas.intake import (
    IntakeCreate, IntakeOut, 
    CounselingPointsUpdate, PharmacistNotesUpdate, DispenseUpdate
)
from services import intake_service
from database import get_db

router = APIRouter(prefix="/intakes", tags=["intakes"])


@router.post("", response_model=IntakeOut)
def create_intake(payload: IntakeCreate, db: Session = Depends(get_db)):
    try:
        return intake_service.create_intake(db, payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating intake: {str(e)}")


@router.get("", response_model=list[IntakeOut])
def list_intakes(
    status: str = Query(None, description="Filter by status"),
    assigned_to: str = Query(None, description="Filter by assigned user"),
    db: Session = Depends(get_db)
):
    intakes = intake_service.list_intakes(db, status=status, assigned_to=assigned_to)
    return intakes


@router.get("/{intake_id}", response_model=IntakeOut)
def get_intake(intake_id: int, db: Session = Depends(get_db)):
    intake = intake_service.get_intake_by_id(db, intake_id)
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return intake


@router.post("/{intake_id}/status", response_model=IntakeOut)
def change_status(intake_id: int, payload: StatusUpdate, db: Session = Depends(get_db)):
    try:
        intake = intake_service.update_status(db, intake_id, payload.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return intake


@router.post("/{intake_id}/assign", response_model=IntakeOut)
def assign_intake(intake_id: int, payload: AssignUser, db: Session = Depends(get_db)):
    intake = intake_service.assign_intake(db, intake_id, payload.user)
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return intake


@router.post("/{intake_id}/counseling", response_model=IntakeOut)
def update_counseling_points(intake_id: int, payload: CounselingPointsUpdate, db: Session = Depends(get_db)):
    intake = intake_service.update_counseling_points(db, intake_id, payload.counseling_points)
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return intake


@router.post("/{intake_id}/pharmacist-notes", response_model=IntakeOut)
def update_pharmacist_notes(intake_id: int, payload: PharmacistNotesUpdate, db: Session = Depends(get_db)):
    intake = intake_service.update_pharmacist_notes(db, intake_id, payload.pharmacist_notes)
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return intake


@router.post("/{intake_id}/dispense", response_model=IntakeOut)
def dispense_medication(intake_id: int, payload: DispenseUpdate, db: Session = Depends(get_db)):
    intake = intake_service.dispense_medication(db, intake_id, payload.dispensed)
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return intake


@router.get("/{intake_id}/check-interactions")
def check_interactions(intake_id: int, db: Session = Depends(get_db)):
    result = intake_service.check_interactions_for_intake(db, intake_id)
    if not result:
        raise HTTPException(status_code=404, detail="Intake not found")
    return result


@router.get("/stats/summary")
def get_statistics(db: Session = Depends(get_db)):
    return intake_service.get_statistics(db)