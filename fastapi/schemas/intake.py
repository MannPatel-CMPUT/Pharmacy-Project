from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Any
from datetime import datetime


class StatusHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    intake_id: int
    from_status: Optional[str] = None
    to_status: str
    changed_at: datetime
    changed_by: Optional[str] = None


class IntakeCreate(BaseModel):
    patient_name: str = Field(..., min_length=1, max_length=100)
    patient_age: Optional[int] = Field(None, ge=0, le=150)
    patient_gender: Optional[str] = Field(None, max_length=32)
    patient_phone: Optional[str] = Field(
        None,
        max_length=40,
        description="Mobile for pickup WhatsApp link; include country code outside +1.",
    )
    patient_allergies: Optional[str] = Field(None, max_length=500)
    medications: str = Field(..., min_length=1)
    current_medications: Optional[str] = None
    notes: Optional[str] = None


class IntakeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_name: str
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    patient_phone: Optional[str] = None
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
    # Workflow (Kroll-style; computed — not DB columns)
    stage_display: str = ""
    pickup_ready: bool = False
    workflow_hint: str = ""


class CounselingPointsUpdate(BaseModel):
    counseling_points: str


class PharmacistNotesUpdate(BaseModel):
    pharmacist_notes: str


class DispenseUpdate(BaseModel):
    dispensed: str = Field(..., pattern="^(yes|no)$")


class EvaluateIntakeRequest(BaseModel):
    patient_name: str = Field(..., min_length=1, max_length=100)
    patient_age: Optional[int] = Field(None, ge=0, le=150)
    patient_gender: Optional[str] = Field(None, max_length=32)
    patient_phone: Optional[str] = Field(None, max_length=40)
    patient_allergies: Optional[str] = Field(None, max_length=500)
    medications: str = Field(..., min_length=1)
    current_medications: Optional[str] = None
    notes: Optional[str] = None
    smoking: Optional[str] = None
    alcohol_use: Optional[str] = None
    renal_status: Optional[str] = None
    hepatic_status: Optional[str] = None
    pregnancy: Optional[str] = None


class EvaluateInteractionItem(BaseModel):
    drug1: str
    drug2: str
    severity: str
    riskFactor: str
    explanation: str
    recommendation: str
    source: Optional[str] = None


class EvaluateIntakeResponse(BaseModel):
    success: bool
    interactions: List[EvaluateInteractionItem]
    allergyWarnings: List[str]
    lifestyleWarnings: List[str]
    overallRisk: str
    error: Optional[str] = None
