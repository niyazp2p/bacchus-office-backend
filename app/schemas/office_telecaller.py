# app/schemas/office_telecaller.py
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.office_telecaller import CallDisposition, SentimentRating
from app.models.office_lead import LeadTier


class LogCallRequest(BaseModel):
    disposition: CallDisposition
    sentiment: SentimentRating = SentimentRating.NEUTRAL
    duration_seconds: int = Field(0, ge=0)
    notes: str = Field(..., min_length=3, max_length=2000)
    scheduled_callback_at: datetime | None = None
    portfolio_sent: bool = False
    proposal_sent: bool = False
    evaluated_tier: LeadTier | None = None


class CallRecordResponse(BaseModel):
    id: UUID
    lead_id: UUID
    caller_id: UUID
    disposition: CallDisposition
    sentiment: SentimentRating
    duration_seconds: int
    notes: str
    scheduled_callback_at: datetime | None
    portfolio_sent: bool
    proposal_sent: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PushToBdmRequest(BaseModel):
    summary_remarks: str = Field(..., min_length=5, max_length=2000)
    confirmed_volume: str | None = None
    priority_flag: bool = False
    final_tier: LeadTier = LeadTier.WARM


class PushToBdmResponse(BaseModel):
    lead_id: UUID
    lead_code: str
    status: str
    assigned_bdm_code: str
    sla_deadline: datetime
    message: str


class CallerStatsResponse(BaseModel):
    total_assigned_active: int
    calls_made_today: int
    connected_calls_today: int
    total_talk_time_minutes: float
    escalated_to_bdm_count: int


class MarkLostRequest(BaseModel):
    loss_reason: str = Field(..., min_length=3, max_length=2000)


class KeepInLoopRequest(BaseModel):
    next_follow_up_at: datetime
    remarks: str = Field(..., min_length=3, max_length=2000)
    updated_tier: LeadTier | None = None


class ManualAssignLeadRequest(BaseModel):
    caller_emp_id: str


class CallerActivityFeedItem(BaseModel):
    timestamp: datetime
    lead_id: UUID
    lead_code: str
    company_name: str
    contact_name: str
    action_type: str
    disposition: str | None = None
    notes: str
    portfolio_sent: bool = False
    proposal_sent: bool = False
    scheduled_callback_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)