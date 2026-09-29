from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.office_operations import ComplianceStatus, DispatchState
from app.models.office_lead import LeadTier, LeadStatus, CommercialModel

class OperationsQueueItem(BaseModel):
    lead_id: UUID
    lead_code: str
    company_name: str
    country: str
    state: str | None
    commercial_model: CommercialModel
    tier: LeadTier
    score: int
    status: LeadStatus
    volume_estimate: str | None
    bdm_remarks: str | None
    compliance_status: ComplianceStatus
    dispatch_state: DispatchState
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AttestationChecklistPayload(BaseModel):
    excise_license_verified: bool = Field(...)
    excise_license_no: str | None = Field(None, max_length=100)
    license_expiry_date: date | None = None
    coo_msds_cleared: bool = Field(...)
    bonded_warehouse_verified: bool = Field(...)
    territory_exclusivity_cleared: bool = Field(...)
    notes: str | None = Field(None, max_length=2000)

class DispatchManifestSignOffPayload(BaseModel):
    dispatch_permit_no: str = Field(..., min_length=3, max_length=100)
    transporter_carrier: str = Field(..., min_length=2, max_length=255)
    vehicle_container_no: str = Field(..., min_length=2, max_length=100)
    customs_seal_no: str | None = Field(None, max_length=100)
    estimated_dispatch_date: date = Field(...)
    locked_margin_pct: float = Field(..., ge=0.0, le=100.0)
    locked_annual_cases: int = Field(..., ge=1)
    clearance_notes: str = Field(..., min_length=5, max_length=2500)

class OperationsClearanceResponse(BaseModel):
    id: UUID
    lead_id: UUID
    operations_head_id: UUID | None
    compliance_status: ComplianceStatus
    dispatch_state: DispatchState
    excise_license_verified: bool
    excise_license_no: str | None
    license_expiry_date: date | None
    coo_msds_cleared: bool
    bonded_warehouse_verified: bool
    territory_exclusivity_cleared: bool
    dispatch_permit_no: str | None
    transporter_carrier: str | None
    vehicle_container_no: str | None
    customs_seal_no: str | None
    estimated_dispatch_date: date | None
    locked_margin_pct: float | None
    locked_annual_cases: int | None
    clearance_notes: str | None
    cleared_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class OperationsKpiSummary(BaseModel):
    pending_compliance_audit: int
    cleared_ready_for_dispatch: int
    converted_accounts: int
    active_holds: int