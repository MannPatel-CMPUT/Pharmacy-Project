from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class IntakeCreate(BaseModel):
    patient_name: str
    patient_age: Optional[int] = None
    patient_allergies: Optional[str] = None
    medications: str
    current_medications: Optional[str] = None
    notes: Optional[str] = None

class IntakeOut(BaseModel):
    id: int
    patient_name: str
    patient_age: Optional[int] = None
    patient_allergies: Optional[str] = None
    medications: str
    current_medications: Optional[str] = None
    notes: Optional[str] = None
    counseling_points: Optional[str] = None
    pharmacist_notes: Optional[str] = None
    drug_interactions: Optional[str] = None
    status: str
    assigned_to: Optional[str] = None
    dispensed: Optional[str] = None
    dispensed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class CounselingPointsUpdate(BaseModel):
    counseling_points: str

class PharmacistNotesUpdate(BaseModel):
    pharmacist_notes: str

class DispenseUpdate(BaseModel):
    dispensed: str  # "yes" or "no"
