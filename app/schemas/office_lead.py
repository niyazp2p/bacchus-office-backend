# app/schemas/office_lead.py
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict, Field
from app.models.office_lead import LeadTier, LeadStatus, CommercialModel


class LeadCreate(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=255)
    contact_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    phone: str | None = Field(None, max_length=50)
    country: str = Field("India", min_length=2, max_length=100)
    state: str | None = Field(None, max_length=100)
    commercial_model: CommercialModel = CommercialModel.DISTRIBUTION
    volume_estimate: str | None = Field(None, max_length=255)


class LeadUpdate(BaseModel):
    company_name: str | None = None
    contact_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    country: str | None = None
    state: str | None = None
    commercial_model: CommercialModel | None = None
    volume_estimate: str | None = None
    caller_remarks: str | None = None
    bdm_remarks: str | None = None
    loss_reason: str | None = None


class LeadPatchStatus(BaseModel):
    status: LeadStatus
    remarks: str | None = None


class LeadResponse(BaseModel):
    id: UUID
    lead_code: str
    company_name: str
    contact_name: str
    email: EmailStr
    phone: str | None
    country: str
    state: str | None
    commercial_model: CommercialModel
    volume_estimate: str | None
    score: int
    tier: LeadTier
    status: LeadStatus
    portfolio_sent: bool = False
    proposal_sent: bool = False
    caller_remarks: str | None
    bdm_remarks: str | None
    loss_reason: str | None
    assigned_caller_id: UUID | None
    assigned_bdm_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoutingResult(BaseModel):
    total_unassigned: int
    total_routed: int
    active_callers_count: int
    allocations: dict[str, int]