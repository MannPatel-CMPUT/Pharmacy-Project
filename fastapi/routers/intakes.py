from schemas.intake_actions import StatusUpdate, AssignUser
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from schemas.intake import (
    IntakeCreate, IntakeOut, StatusHistoryEntry,
    CounselingPointsUpdate, PharmacistNotesUpdate, DispenseUpdate,
    EvaluateIntakeRequest, EvaluateIntakeResponse,
)
from services import intake_service, auth_service
from database import get_db


def _current_username(request: Request) -> Optional[str]:
    """Best-effort: extract logged-in username from the session cookie."""
    raw = request.cookies.get(auth_service.COOKIE_NAME)
    if not raw:
        return None
    payload = auth_service.decode_token(raw)
    if not payload:
        return None
    return str(payload.get("u") or "") or None

router = APIRouter(prefix="/intakes", tags=["intakes"])


@router.post("", response_model=IntakeOut, status_code=201)
def create_intake(payload: IntakeCreate, request: Request, db: Session = Depends(get_db)):
    try:
        intake = intake_service.create_intake(db, payload, created_by=_current_username(request))
        return intake_service.enrich_intake_out(intake)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating intake: {str(e)}")


@router.post("/evaluate", response_model=EvaluateIntakeResponse)
def evaluate_intake(payload: EvaluateIntakeRequest, db: Session = Depends(get_db)):
    """
    Evaluate drug interactions, allergy warnings, and lifestyle cautions without saving an intake.
    Uses the local drug_interactions table (from ``DRUG_INTERACTIONS_CSV`` at server start).
    """
    result = intake_service.evaluate_intake_interactions(db, payload)
    return result


@router.get("", response_model=List[IntakeOut])
def list_intakes(
    status: Optional[str] = Query(None, description="Filter by status"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned user"),
    search: Optional[str] = Query(None, description="Search by patient name"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of records to return"),
    db: Session = Depends(get_db)
):
    rows = intake_service.list_intakes(db, status=status, assigned_to=assigned_to, search=search, skip=skip, limit=limit)
    return [intake_service.enrich_intake_out(i) for i in rows]


@router.get("/stats/summary")
def get_statistics(db: Session = Depends(get_db)):
    return intake_service.get_statistics(db)


@router.post("/{intake_id}/check-interactions")
def check_interactions(intake_id: int, db: Session = Depends(get_db)):
    """Re-run interaction detection and refresh counseling (not cacheable as GET)."""
    result = intake_service.check_interactions_for_intake(db, intake_id)
    if not result:
        raise HTTPException(status_code=404, detail="Intake not found")
    return result


@router.get("/{intake_id}", response_model=IntakeOut)
def get_intake(intake_id: int, db: Session = Depends(get_db)):
    intake = intake_service.get_intake_by_id(db, intake_id)
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return intake_service.enrich_intake_out(intake)


@router.delete("/{intake_id}", status_code=204)
def cancel_intake(intake_id: int, db: Session = Depends(get_db)):
    deleted = intake_service.cancel_intake(db, intake_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Intake not found")


@router.post("/{intake_id}/status", response_model=IntakeOut)
def change_status(intake_id: int, payload: StatusUpdate, request: Request, db: Session = Depends(get_db)):
    try:
        intake = intake_service.update_status(
            db, intake_id, payload.status, changed_by=_current_username(request)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return intake_service.enrich_intake_out(intake)


@router.get("/{intake_id}/history", response_model=List[StatusHistoryEntry])
def get_status_history(intake_id: int, db: Session = Depends(get_db)):
    intake = intake_service.get_intake_by_id(db, intake_id)
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return intake_service.get_status_history(db, intake_id)


@router.post("/{intake_id}/assign", response_model=IntakeOut)
def assign_intake(intake_id: int, payload: AssignUser, db: Session = Depends(get_db)):
    intake = intake_service.assign_intake(db, intake_id, payload.user)
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return intake_service.enrich_intake_out(intake)


@router.post("/{intake_id}/counseling", response_model=IntakeOut)
def update_counseling_points(intake_id: int, payload: CounselingPointsUpdate, db: Session = Depends(get_db)):
    intake = intake_service.update_counseling_points(db, intake_id, payload.counseling_points)
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return intake_service.enrich_intake_out(intake)


@router.post("/{intake_id}/pharmacist-notes", response_model=IntakeOut)
def update_pharmacist_notes(intake_id: int, payload: PharmacistNotesUpdate, db: Session = Depends(get_db)):
    intake = intake_service.update_pharmacist_notes(db, intake_id, payload.pharmacist_notes)
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return intake_service.enrich_intake_out(intake)


@router.post("/{intake_id}/dispense", response_model=IntakeOut)
def dispense_medication(intake_id: int, payload: DispenseUpdate, request: Request, db: Session = Depends(get_db)):
    intake = intake_service.dispense_medication(db, intake_id, payload.dispensed, changed_by=_current_username(request))
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return intake_service.enrich_intake_out(intake)


@router.get("/{intake_id}/permissions")
def check_intake_permissions(intake_id: int, request: Request, db: Session = Depends(get_db)):
    """Check if current user can modify this intake."""
    intake = intake_service.get_intake_by_id(db, intake_id)
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    
    username = _current_username(request)
    can_modify = intake_service.can_user_modify_intake(intake, username)
    
    return {
        "can_modify": can_modify,
        "created_by": intake.created_by,
        "assigned_to": intake.assigned_to,
        "current_user": username
    }
