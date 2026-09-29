from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.office_lead import LeadStatus, LeadTier
from app.models.office_auth import OfficeRole

class MacroPipelineTelemetry(BaseModel):
    total_leads: int
    unassigned_new: int
    active_telecaller_pool: int
    pending_bdm_review: int
    bdm_approved: int
    converted_dispatched: int
    parked_or_lost: int
    sla_breaches_active: int
    average_locked_margin_pct: float
    total_projected_cases: int

class StaffEfficiencyItem(BaseModel):
    emp_code: str
    name: str
    role: OfficeRole
    department: str
    active_load: int
    completed_actions: int
    success_rate_pct: float

class ReassignmentOverridePayload(BaseModel):
    lead_ids: list[UUID] = Field(..., min_length=1)
    new_caller_id: UUID | None = None
    new_bdm_id: UUID | None = None
    override_status: LeadStatus | None = None
    audit_reason: str = Field(..., min_length=5, max_length=1000)

class ReassignmentOverrideResponse(BaseModel):
    success: bool
    modified_count: int
    message: str

class AuditLogItem(BaseModel):
    id: UUID
    actor_email: str | None
    actor_role: str | None
    method: str
    route_path: str
    status_code: int
    latency_ms: int
    client_ip: str | None
    action_description: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)