# app/api/v1/office_telecaller.py
import uuid
from datetime import datetime, timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.office_auth import OfficeUser, OfficeEmployee, OfficeRole
from app.models.office_lead import OfficeLead, LeadStatus, LeadTier
from app.models.office_telecaller import OfficeCallRecord, CallDisposition
from app.schemas.office_telecaller import (
    LogCallRequest,
    CallRecordResponse,
    PushToBdmRequest,
    PushToBdmResponse,
    CallerStatsResponse,
    MarkLostRequest,
    KeepInLoopRequest,
    ManualAssignLeadRequest,
    CallerActivityFeedItem,
)
from app.schemas.office_lead import LeadResponse
from app.dependencies.office_auth import get_current_user, require_roles

router = APIRouter(prefix="/caller", tags=["Office Telecaller Desk Operations"])


# 1. Frontline Queue
@router.get("/my-bucket", response_model=list[LeadResponse])
async def get_my_caller_bucket(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=150),
    offset: int = Query(0, ge=0),
):
    if not current_user.employee_profile:
        return []

    stmt = (
        select(OfficeLead)
        .where(
            OfficeLead.assigned_caller_id == current_user.employee_profile.id,
            OfficeLead.status.in_([LeadStatus.ROUTED_TO_CALLER, LeadStatus.CONTACTED]),
        )
        .order_by(desc(OfficeLead.tier), OfficeLead.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


# 2. Performance Stats
@router.get("/performance-stats", response_model=CallerStatsResponse)
async def get_caller_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(get_current_user)],
):
    if not current_user.employee_profile:
        return CallerStatsResponse(
            total_assigned_active=0,
            calls_made_today=0,
            connected_calls_today=0,
            total_talk_time_minutes=0.0,
            escalated_to_bdm_count=0,
        )

    emp_id = current_user.employee_profile.id
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    active_cnt = await db.scalar(
        select(func.count(OfficeLead.id)).where(
            OfficeLead.assigned_caller_id == emp_id,
            OfficeLead.status.in_([LeadStatus.ROUTED_TO_CALLER, LeadStatus.CONTACTED]),
        )
    ) or 0

    today_calls = await db.scalar(
        select(func.count(OfficeCallRecord.id)).where(
            OfficeCallRecord.caller_id == emp_id,
            OfficeCallRecord.created_at >= today_start,
        )
    ) or 0

    connected_calls = await db.scalar(
        select(func.count(OfficeCallRecord.id)).where(
            OfficeCallRecord.caller_id == emp_id,
            OfficeCallRecord.disposition == CallDisposition.CALL_RECEIVED,
            OfficeCallRecord.created_at >= today_start,
        )
    ) or 0

    talk_seconds = await db.scalar(
        select(func.sum(OfficeCallRecord.duration_seconds)).where(
            OfficeCallRecord.caller_id == emp_id,
            OfficeCallRecord.created_at >= today_start,
        )
    ) or 0

    escalated_cnt = await db.scalar(
        select(func.count(OfficeLead.id)).where(
            OfficeLead.assigned_caller_id == emp_id,
            OfficeLead.status == LeadStatus.PENDING_BDM_REVIEW,
        )
    ) or 0

    return CallerStatsResponse(
        total_assigned_active=active_cnt,
        calls_made_today=today_calls,
        connected_calls_today=connected_calls,
        total_talk_time_minutes=round(talk_seconds / 60.0, 1),
        escalated_to_bdm_count=escalated_cnt,
    )


# 3. Log Call with Checkbox Document Tracking
@router.post("/leads/{lead_id}/calls", response_model=CallRecordResponse)
async def log_call_record(
    lead_id: uuid.UUID,
    payload: LogCallRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(get_current_user)],
):
    if not current_user.employee_profile:
        raise HTTPException(status_code=400, detail="User has no linked employee profile.")

    lead = await db.scalar(select(OfficeLead).where(OfficeLead.id == lead_id))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    now = datetime.utcnow()
    # Update lead status to CONTACTED if it was ROUTED_TO_CALLER
    if lead.status == LeadStatus.ROUTED_TO_CALLER:
        lead.status = LeadStatus.CONTACTED

    # Track documents sent checkboxes
    if payload.portfolio_sent:
        lead.portfolio_sent = True
        lead.portfolio_sent_at = now

    if payload.proposal_sent:
        lead.proposal_sent = True
        lead.proposal_sent_at = now

    # Dynamic tier adjustment if evaluated by caller
    if payload.evaluated_tier:
        lead.tier = payload.evaluated_tier

    lead.caller_remarks = payload.notes
    lead.updated_at = now

    call_log = OfficeCallRecord(
        lead_id=lead.id,
        caller_id=current_user.employee_profile.id,
        disposition=payload.disposition,
        sentiment=payload.sentiment,
        duration_seconds=payload.duration_seconds,
        notes=payload.notes,
        scheduled_callback_at=payload.scheduled_callback_at,
        portfolio_sent=payload.portfolio_sent,
        proposal_sent=payload.proposal_sent,
    )
    db.add(call_log)
    await db.commit()
    await db.refresh(call_log)
    return call_log


# 4. Get Lead Call History
@router.get("/leads/{lead_id}/calls", response_model=list[CallRecordResponse])
async def get_lead_call_history(
    lead_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(get_current_user)],
):
    stmt = (
        select(OfficeCallRecord)
        .where(OfficeCallRecord.lead_id == lead_id)
        .order_by(desc(OfficeCallRecord.created_at))
    )
    records = (await db.execute(stmt)).scalars().all()
    return records


# 5. Handshake: Push to BDM (24-hour review window)
@router.post("/leads/{lead_id}/push-to-bdm", response_model=PushToBdmResponse)
async def push_lead_to_bdm(
    lead_id: uuid.UUID,
    payload: PushToBdmRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(get_current_user)],
):
    if not current_user.employee_profile:
        raise HTTPException(status_code=400, detail="Missing linked employee profile.")

    caller = current_user.employee_profile
    if not caller.reporting_to_id:
        # Fallback: Find any active BDM if direct supervisor is unassigned
        supervisor_bdm = await db.scalar(
            select(OfficeEmployee)
            .join(OfficeUser, OfficeEmployee.user_id == OfficeUser.id)
            .where(OfficeUser.role == OfficeRole.BDM, OfficeUser.is_active.is_(True))
            .limit(1)
        )
    else:
        supervisor_bdm = await db.scalar(
            select(OfficeEmployee).where(OfficeEmployee.id == caller.reporting_to_id)
        )

    if not supervisor_bdm:
        raise HTTPException(status_code=400, detail="No designated BDM supervisor found to route this lead.")

    lead = await db.scalar(select(OfficeLead).where(OfficeLead.id == lead_id))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    lead.status = LeadStatus.PENDING_BDM_REVIEW
    lead.assigned_bdm_id = supervisor_bdm.id
    lead.caller_remarks = payload.summary_remarks
    lead.tier = payload.final_tier
    if payload.confirmed_volume:
        lead.volume_estimate = payload.confirmed_volume

    sla_deadline = datetime.utcnow() + timedelta(hours=24)
    await db.commit()

    return PushToBdmResponse(
        lead_id=lead.id,
        lead_code=lead.lead_code,
        status=lead.status.value,
        assigned_bdm_code=supervisor_bdm.emp_code,
        sla_deadline=sla_deadline,
        message=f"Lead successfully bound to BDM {supervisor_bdm.emp_code}. 24-hr review SLA active.",
    )


# 6. Handshake: Mark Lead Lost
@router.post("/leads/{lead_id}/mark-lost", response_model=LeadResponse)
async def mark_lead_lost(
    lead_id: uuid.UUID,
    payload: MarkLostRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(get_current_user)],
):
    lead = await db.scalar(select(OfficeLead).where(OfficeLead.id == lead_id))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    lead.status = LeadStatus.LOST
    lead.loss_reason = payload.loss_reason
    lead.updated_at = datetime.utcnow()

    # Log an exit record
    if current_user.employee_profile:
        exit_log = OfficeCallRecord(
            lead_id=lead.id,
            caller_id=current_user.employee_profile.id,
            disposition=CallDisposition.CALL_DECLINED,
            sentiment=SentimentRating.HOSTILE,
            duration_seconds=0,
            notes=f"LEAD MARKED LOST: {payload.loss_reason}",
        )
        db.add(exit_log)

    await db.commit()
    await db.refresh(lead)
    return lead


# 7. Handshake: Keep in Loop (Retry / Follow-Up Cadence)
@router.post("/leads/{lead_id}/keep-in-loop", response_model=LeadResponse)
async def keep_lead_in_loop(
    lead_id: uuid.UUID,
    payload: KeepInLoopRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(get_current_user)],
):
    lead = await db.scalar(select(OfficeLead).where(OfficeLead.id == lead_id))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    lead.status = LeadStatus.CONTACTED
    lead.caller_remarks = payload.remarks
    if payload.updated_tier:
        lead.tier = payload.updated_tier

    lead.updated_at = datetime.utcnow()

    if current_user.employee_profile:
        loop_log = OfficeCallRecord(
            lead_id=lead.id,
            caller_id=current_user.employee_profile.id,
            disposition=CallDisposition.CALL_AFTER_SOMETIME,
            sentiment=SentimentRating.NEUTRAL,
            duration_seconds=0,
            notes=f"CADENCE SCHEDULED: {payload.remarks}",
            scheduled_callback_at=payload.next_follow_up_at,
        )
        db.add(loop_log)

    await db.commit()
    await db.refresh(lead)
    return lead


# 8. Admin Action: Manual Lead Assignment
# In app/api/v1/office_telecaller.py

@router.patch("/leads/{lead_id}/assign-manually", response_model=LeadResponse)
async def manual_assign_lead(
    lead_id: uuid.UUID,
    payload: ManualAssignLeadRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        OfficeUser,
        Depends(require_roles([OfficeRole.SUPER_ADMIN, OfficeRole.COO, OfficeRole.OPERATIONS_HEAD])),
    ],
):
    lead = await db.scalar(select(OfficeLead).where(OfficeLead.id == lead_id))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    # 1. Resolve employee by UUID or emp_code
    target_emp = None
    try:
        parsed_uuid = uuid.UUID(payload.caller_emp_id)
        target_emp = await db.scalar(
            select(OfficeEmployee).where(OfficeEmployee.id == parsed_uuid)
        )
    except (ValueError, AttributeError):
        target_emp = await db.scalar(
            select(OfficeEmployee).where(OfficeEmployee.emp_code == payload.caller_emp_id)
        )

    if not target_emp:
        raise HTTPException(
            status_code=404,
            detail=f"Target Telecaller '{payload.caller_emp_id}' does not exist.",
        )

    # 2. Assign lead and transition status
    lead.assigned_caller_id = target_emp.id
    lead.status = LeadStatus.ROUTED_TO_CALLER
    lead.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(lead)
    return lead

# 9. Admin Oversight: Chronological Telecaller Activity Feed
# app/api/v1/office_telecaller.py

@router.get("/activity-feed/{caller_id}", response_model=list[CallerActivityFeedItem])
async def get_caller_activity_feed(
    caller_id: str,  # Change from uuid.UUID to str so TC-01 or UUID both pass
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        OfficeUser, 
        Depends(require_roles([OfficeRole.SUPER_ADMIN, OfficeRole.COO, OfficeRole.OPERATIONS_HEAD]))
    ],
    limit: int = Query(50, ge=1, le=200),
):
    # Try resolving whether caller_id is a UUID or an emp_code
    target_emp = None
    try:
        parsed_uuid = uuid.UUID(caller_id)
        target_emp = await db.scalar(select(OfficeEmployee).where(OfficeEmployee.id == parsed_uuid))
    except (ValueError, AttributeError):
        # It's an emp_code like 'TC-01'
        target_emp = await db.scalar(select(OfficeEmployee).where(OfficeEmployee.emp_code == caller_id))

    if not target_emp:
        return []

    stmt = (
        select(OfficeCallRecord, OfficeLead)
        .join(OfficeLead, OfficeCallRecord.lead_id == OfficeLead.id)
        .where(OfficeCallRecord.caller_id == target_emp.id)
        .order_by(desc(OfficeCallRecord.created_at))
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    feed = []
    for call, lead in rows:
        feed.append(
            CallerActivityFeedItem(
                timestamp=call.created_at,
                lead_id=lead.id,
                lead_code=lead.lead_code,
                company_name=lead.company_name,
                contact_name=lead.contact_name,
                action_type=f"CALL: {call.disposition.value}",
                disposition=call.disposition.value,
                notes=call.notes,
                portfolio_sent=call.portfolio_sent,
                proposal_sent=call.proposal_sent,
                scheduled_callback_at=call.scheduled_callback_at,
            )
        )
    return feed