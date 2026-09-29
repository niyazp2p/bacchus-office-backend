from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.office_lead import LeadTier, LeadStatus, CommercialModel
from app.models.office_bdm import (
    BdmAction,
    ContainerSpec,
    IncoTerms,
    PaymentTerms,
    RejectionReason,
    RecycleDisposition,
)
from app.schemas.office_telecaller import CallRecordResponse

class BdmLeadQueueItem(BaseModel):
    id: UUID
    lead_code: str
    company_name: str
    contact_name: str
    email: str
    phone: str | None
    country: str
    state: str | None
    commercial_model: CommercialModel
    volume_estimate: str | None
    tier: LeadTier
    score: int
    status: LeadStatus
    caller_remarks: str | None
    assigned_caller_code: str | None
    escalated_at: datetime
    sla_deadline: datetime
    hours_remaining: float
    is_sla_breached: bool

    model_config = ConfigDict(from_attributes=True)

class LeadReviewAcceptPayload(BaseModel):
    projected_annual_cases: int = Field(..., ge=1)
    container_spec: ContainerSpec
    inco_terms: IncoTerms
    payment_terms: PaymentTerms
    estimated_margin_pct: float = Field(..., ge=0.0, le=100.0)
    remarks: str = Field(..., min_length=5, max_length=2500)

class LeadReviewRejectPayload(BaseModel):
    rejection_reason: RejectionReason
    recycle_disposition: RecycleDisposition
    remarks: str = Field(..., min_length=5, max_length=2500)
    rework_instructions: str | None = Field(None, max_length=2000)

class BdmReviewResponse(BaseModel):
    id: UUID
    lead_id: UUID
    bdm_id: UUID
    action: BdmAction
    projected_annual_cases: int | None
    container_spec: ContainerSpec | None
    inco_terms: IncoTerms | None
    payment_terms: PaymentTerms | None
    estimated_margin_pct: float | None
    rejection_reason: RejectionReason | None
    recycle_disposition: RecycleDisposition | None
    rework_instructions: str | None
    remarks: str
    sla_breached: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class BdmLeadDetailView(BaseModel):
    lead_id: UUID
    lead_code: str
    company_name: str
    contact_name: str
    email: str
    phone: str | None
    country: str
    state: str | None
    commercial_model: CommercialModel
    tier: LeadTier
    score: int
    status: LeadStatus
    volume_estimate: str | None
    caller_remarks: str | None
    bdm_remarks: str | None
    call_history: list[CallRecordResponse]
    past_reviews: list[BdmReviewResponse]
    created_at: datetime

class BdmTelemetryResponse(BaseModel):
    total_pending_review: int
    total_accepted: int
    total_rejected: int
    total_recycled_to_callers: int
    acceptance_rate_pct: float
    sla_breaches_count: int