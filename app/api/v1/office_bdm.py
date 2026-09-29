import uuid
from datetime import datetime, timezone, timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, desc, or_, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.office_auth import OfficeUser, OfficeEmployee, OfficeRole
from app.models.office_lead import OfficeLead, LeadStatus
from app.models.office_telecaller import OfficeCallRecord
from app.models.office_bdm import (
    OfficeBdmReview,
    BdmAction,
    RecycleDisposition,
)
from app.schemas.office_bdm import (
    BdmLeadQueueItem,
    LeadReviewAcceptPayload,
    LeadReviewRejectPayload,
    BdmReviewResponse,
    BdmLeadDetailView,
    BdmTelemetryResponse,
)
from app.dependencies.office_auth import get_current_user

router = APIRouter(prefix="/bdm", tags=["Office BDM Triage Desk"])

def get_bdm_employee(user: OfficeUser) -> OfficeEmployee:
    if user.role != OfficeRole.BDM and user.role != OfficeRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Endpoint accessible only to Business Development Managers.")
    if not user.employee_profile:
        raise HTTPException(status_code=400, detail="User does not have an active employee profile node.")
    return user.employee_profile

# 1. BDM Review Queue (Active Leads in PENDING_BDM_REVIEW)
@router.get("/queue", response_model=list[BdmLeadQueueItem])
async def get_bdm_review_queue(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(get_current_user)],
):
    emp = get_bdm_employee(current_user)

    # Scoping: BDM sees leads assigned directly or submitted by their reporting telecallers
    subordinate_caller_ids = (
        select(OfficeEmployee.id).where(OfficeEmployee.reporting_to_id == emp.id)
    )

    stmt = (
        select(OfficeLead, OfficeEmployee.emp_code)
        .outerjoin(OfficeEmployee, OfficeLead.assigned_caller_id == OfficeEmployee.id)
        .where(
            OfficeLead.status == LeadStatus.PENDING_BDM_REVIEW,
            or_(
                OfficeLead.assigned_bdm_id == emp.id,
                OfficeLead.assigned_caller_id.in_(subordinate_caller_ids),
                current_user.role == OfficeRole.SUPER_ADMIN,
            ),
        )
        .order_by(desc(OfficeLead.tier), OfficeLead.updated_at.asc())
    )

    results = (await db.execute(stmt)).all()
    queue_items = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for lead, caller_code in results:
        # Compute SLA window from lead's last update timestamp (when pushed to BDM)
        escalated_at = lead.updated_at
        sla_deadline = escalated_at + timedelta(hours=24)
        diff_seconds = (sla_deadline - now).total_seconds()
        hours_remaining = round(diff_seconds / 3600.0, 2)
        is_breached = hours_remaining < 0

        queue_items.append(
            BdmLeadQueueItem(
                id=lead.id,
                lead_code=lead.lead_code,
                company_name=lead.company_name,
                contact_name=lead.contact_name,
                email=lead.email,
                phone=lead.phone,
                country=lead.country,
                state=lead.state,
                commercial_model=lead.commercial_model,
                volume_estimate=lead.volume_estimate,
                tier=lead.tier,
                score=lead.score,
                status=lead.status,
                caller_remarks=lead.caller_remarks,
                assigned_caller_code=caller_code,
                escalated_at=escalated_at,
                sla_deadline=sla_deadline,
                hours_remaining=hours_remaining,
                is_sla_breached=is_breached,
            )
        )
    return queue_items

# 2. Complete Lead Triage Dossier (Audit calls + Past reviews)
@router.get("/leads/{lead_id}", response_model=BdmLeadDetailView)
async def get_lead_review_dossier(
    lead_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(get_current_user)],
):
    emp = get_bdm_employee(current_user)

    lead = await db.scalar(select(OfficeLead).where(OfficeLead.id == lead_id))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    # Call history
    call_stmt = select(OfficeCallRecord).where(OfficeCallRecord.lead_id == lead.id).order_by(desc(OfficeCallRecord.created_at))
    calls = (await db.execute(call_stmt)).scalars().all()

    # Past reviews
    rev_stmt = select(OfficeBdmReview).where(OfficeBdmReview.lead_id == lead.id).order_by(desc(OfficeBdmReview.created_at))
    reviews = (await db.execute(rev_stmt)).scalars().all()

    return BdmLeadDetailView(
        lead_id=lead.id,
        lead_code=lead.lead_code,
        company_name=lead.company_name,
        contact_name=lead.contact_name,
        email=lead.email,
        phone=lead.phone,
        country=lead.country,
        state=lead.state,
        commercial_model=lead.commercial_model,
        tier=lead.tier,
        score=lead.score,
        status=lead.status,
        volume_estimate=lead.volume_estimate,
        caller_remarks=lead.caller_remarks,
        bdm_remarks=lead.bdm_remarks,
        call_history=calls,
        past_reviews=reviews,
        created_at=lead.created_at,
    )

# 3. Acceptance Handshake: Escalate to Operations Head
@router.post("/leads/{lead_id}/accept", response_model=BdmReviewResponse, status_code=status.HTTP_201_CREATED)
async def accept_and_escalate_lead(
    lead_id: uuid.UUID,
    payload: LeadReviewAcceptPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(get_current_user)],
):
    emp = get_bdm_employee(current_user)

    lead = await db.scalar(select(OfficeLead).where(OfficeLead.id == lead_id))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    if lead.status != LeadStatus.PENDING_BDM_REVIEW and current_user.role != OfficeRole.SUPER_ADMIN:
        raise HTTPException(status_code=400, detail=f"Lead is not in PENDING_BDM_REVIEW state (Current: {lead.status.value}).")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sla_deadline = lead.updated_at + timedelta(hours=24)
    sla_breached = now > sla_deadline

    # Create audit review record
    review = OfficeBdmReview(
        lead_id=lead.id,
        bdm_id=emp.id,
        action=BdmAction.ACCEPT,
        projected_annual_cases=payload.projected_annual_cases,
        container_spec=payload.container_spec,
        inco_terms=payload.inco_terms,
        payment_terms=payload.payment_terms,
        estimated_margin_pct=payload.estimated_margin_pct,
        remarks=payload.remarks.strip(),
        sla_breached=sla_breached,
    )
    db.add(review)

    # Update Lead State Machine
    lead.status = LeadStatus.BDM_ACCEPTED
    lead.assigned_bdm_id = emp.id
    lead.bdm_remarks = (
        f"[ACCEPTED by {emp.emp_code}] Margin: {payload.estimated_margin_pct}% | "
        f"Cases: {payload.projected_annual_cases}/yr | {payload.container_spec.value} | "
        f"{payload.inco_terms.value} | Terms: {payload.payment_terms.value}. "
        f"Notes: {payload.remarks.strip()}"
    )

    await db.commit()
    await db.refresh(review)
    return review

# 4. Reject & Recycle Loop Handshake
@router.post("/leads/{lead_id}/reject", response_model=BdmReviewResponse, status_code=status.HTTP_201_CREATED)
async def reject_and_recycle_lead(
    lead_id: uuid.UUID,
    payload: LeadReviewRejectPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(get_current_user)],
):
    emp = get_bdm_employee(current_user)

    lead = await db.scalar(select(OfficeLead).where(OfficeLead.id == lead_id))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    if lead.status != LeadStatus.PENDING_BDM_REVIEW and current_user.role != OfficeRole.SUPER_ADMIN:
        raise HTTPException(status_code=400, detail=f"Lead is not in PENDING_BDM_REVIEW state (Current: {lead.status.value}).")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sla_deadline = lead.updated_at + timedelta(hours=24)
    sla_breached = now > sla_deadline

    # Create audit review record
    review = OfficeBdmReview(
        lead_id=lead.id,
        bdm_id=emp.id,
        action=BdmAction.REJECT,
        rejection_reason=payload.rejection_reason,
        recycle_disposition=payload.recycle_disposition,
        rework_instructions=payload.rework_instructions.strip() if payload.rework_instructions else None,
        remarks=payload.remarks.strip(),
        sla_breached=sla_breached,
    )
    db.add(review)

    # Demote Lead Score & Route Disposition
    lead.score = max(0, lead.score - 25)
    lead.bdm_remarks = f"[REJECTED: {payload.rejection_reason.value}] {payload.remarks.strip()}"

    if payload.recycle_disposition == RecycleDisposition.RETURN_TO_TELECALLER:
        lead.status = LeadStatus.ROUTED_TO_CALLER
        lead.loss_reason = None
        if payload.rework_instructions:
            lead.caller_remarks = f"[BDM REWORK ORDER]: {payload.rework_instructions.strip()}"
    elif payload.recycle_disposition == RecycleDisposition.PARK_INDEFINITELY:
        lead.status = LeadStatus.PARKED
        lead.loss_reason = f"Parked by BDM ({emp.emp_code}): {payload.rejection_reason.value}"
    elif payload.recycle_disposition == RecycleDisposition.MARK_LOST:
        lead.status = LeadStatus.LOST
        lead.loss_reason = f"Marked Lost by BDM ({emp.emp_code}): {payload.rejection_reason.value}"

    await db.commit()
    await db.refresh(review)
    return review

# 5. BDM Telemetry & SLA Tracking
@router.get("/telemetry", response_model=BdmTelemetryResponse)
async def get_bdm_telemetry(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(get_current_user)],
):
    emp = get_bdm_employee(current_user)

    subordinate_caller_ids = (
        select(OfficeEmployee.id).where(OfficeEmployee.reporting_to_id == emp.id)
    )

    # Total pending
    pending_stmt = select(func.count(OfficeLead.id)).where(
        OfficeLead.status == LeadStatus.PENDING_BDM_REVIEW,
        or_(
            OfficeLead.assigned_bdm_id == emp.id,
            OfficeLead.assigned_caller_id.in_(subordinate_caller_ids),
        ),
    )
    total_pending = (await db.scalar(pending_stmt)) or 0

    # Reviews breakdown
    accepted_stmt = select(func.count(OfficeBdmReview.id)).where(
        OfficeBdmReview.bdm_id == emp.id,
        OfficeBdmReview.action == BdmAction.ACCEPT,
    )
    total_accepted = (await db.scalar(accepted_stmt)) or 0

    rejected_stmt = select(func.count(OfficeBdmReview.id)).where(
        OfficeBdmReview.bdm_id == emp.id,
        OfficeBdmReview.action == BdmAction.REJECT,
    )
    total_rejected = (await db.scalar(rejected_stmt)) or 0

    recycled_stmt = select(func.count(OfficeBdmReview.id)).where(
        OfficeBdmReview.bdm_id == emp.id,
        OfficeBdmReview.recycle_disposition == RecycleDisposition.RETURN_TO_TELECALLER,
    )
    total_recycled = (await db.scalar(recycled_stmt)) or 0

    sla_breaches_stmt = select(func.count(OfficeBdmReview.id)).where(
        OfficeBdmReview.bdm_id == emp.id,
        OfficeBdmReview.sla_breached.is_(True),
    )
    sla_breaches = (await db.scalar(sla_breaches_stmt)) or 0

    total_reviewed = total_accepted + total_rejected
    acceptance_rate = round((total_accepted / total_reviewed * 100.0), 2) if total_reviewed > 0 else 0.0

    return BdmTelemetryResponse(
        total_pending_review=total_pending,
        total_accepted=total_accepted,
        total_rejected=total_rejected,
        total_recycled_to_callers=total_recycled,
        acceptance_rate_pct=acceptance_rate,
        sla_breaches_count=sla_breaches,
    )