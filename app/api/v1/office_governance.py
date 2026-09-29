import uuid
from datetime import datetime, timezone, timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, desc, or_, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.office_auth import OfficeUser, OfficeEmployee, OfficeRole
from app.models.office_lead import OfficeLead, LeadStatus
from app.models.office_bdm import OfficeBdmReview
from app.models.office_operations import OfficeOperationsClearance, DispatchState
from app.models.office_audit import OfficeAuditLog
from app.schemas.office_governance import (
    MacroPipelineTelemetry,
    StaffEfficiencyItem,
    ReassignmentOverridePayload,
    ReassignmentOverrideResponse,
    AuditLogItem,
)
from app.dependencies.office_auth import require_roles

router = APIRouter(prefix="/governance", tags=["Executive Command & SuperAdmin Governance"])

EXECUTIVE_ROLES = [OfficeRole.SUPER_ADMIN, OfficeRole.COO]

# 1. Macro Pipeline & Financial Velocity Telemetry
@router.get("/macro-hud", response_model=MacroPipelineTelemetry)
async def get_macro_executive_hud(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(require_roles(EXECUTIVE_ROLES))],
):
    # Total count
    total_leads = (await db.scalar(select(func.count(OfficeLead.id)))) or 0

    # Stage breakdowns
    new_count = (await db.scalar(select(func.count(OfficeLead.id)).where(OfficeLead.status == LeadStatus.NEW))) or 0
    telecaller_active = (await db.scalar(select(func.count(OfficeLead.id)).where(
        OfficeLead.status.in_([LeadStatus.ROUTED_TO_CALLER, LeadStatus.CONTACTED])
    ))) or 0
    bdm_review = (await db.scalar(select(func.count(OfficeLead.id)).where(
        OfficeLead.status == LeadStatus.PENDING_BDM_REVIEW
    ))) or 0
    bdm_approved = (await db.scalar(select(func.count(OfficeLead.id)).where(
        OfficeLead.status == LeadStatus.BDM_ACCEPTED
    ))) or 0
    converted = (await db.scalar(select(func.count(OfficeLead.id)).where(
        OfficeLead.status == LeadStatus.CONVERTED
    ))) or 0
    parked_lost = (await db.scalar(select(func.count(OfficeLead.id)).where(
        OfficeLead.status.in_([LeadStatus.PARKED, LeadStatus.LOST])
    ))) or 0

    # Active SLA Breaches (Pending BDM review older than 24h)
    sla_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    active_breaches = (await db.scalar(select(func.count(OfficeLead.id)).where(
        OfficeLead.status == LeadStatus.PENDING_BDM_REVIEW,
        OfficeLead.updated_at < sla_cutoff
    ))) or 0

    # Locked Margins & Volume from Cleared Dispatches
    margin_query = select(
        func.avg(OfficeOperationsClearance.locked_margin_pct),
        func.sum(OfficeOperationsClearance.locked_annual_cases)
    ).where(OfficeOperationsClearance.dispatch_state == DispatchState.CLEARED_FOR_DISPATCH)
    
    margin_res = (await db.execute(margin_query)).first()
    avg_margin = round(margin_res[0], 2) if margin_res and margin_res[0] is not None else 0.0
    total_cases = margin_res[1] if margin_res and margin_res[1] is not None else 0

    return MacroPipelineTelemetry(
        total_leads=total_leads,
        unassigned_new=new_count,
        active_telecaller_pool=telecaller_active,
        pending_bdm_review=bdm_review,
        bdm_approved=bdm_approved,
        converted_dispatched=converted,
        parked_or_lost=parked_lost,
        sla_breaches_active=active_breaches,
        average_locked_margin_pct=avg_margin,
        total_projected_cases=total_cases,
    )

# 2. Staff Efficiency & Workload Matrix
@router.get("/staff-efficiency", response_model=list[StaffEfficiencyItem])
async def get_staff_efficiency_matrix(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(require_roles(EXECUTIVE_ROLES))],
):
    stmt = (
        select(OfficeEmployee, OfficeUser)
        .join(OfficeUser, OfficeEmployee.user_id == OfficeUser.id)
        .where(OfficeUser.role.in_([OfficeRole.TELECALLER, OfficeRole.BDM]))
    )
    records = (await db.execute(stmt)).all()
    metrics = []

    for emp, usr in records:
        if usr.role == OfficeRole.TELECALLER:
            active_load = (await db.scalar(
                select(func.count(OfficeLead.id)).where(
                    OfficeLead.assigned_caller_id == emp.id,
                    OfficeLead.status.in_([LeadStatus.ROUTED_TO_CALLER, LeadStatus.CONTACTED])
                )
            )) or 0
            completed = (await db.scalar(
                select(func.count(OfficeLead.id)).where(
                    OfficeLead.assigned_caller_id == emp.id,
                    OfficeLead.status.in_([LeadStatus.PENDING_BDM_REVIEW, LeadStatus.BDM_ACCEPTED, LeadStatus.CONVERTED])
                )
            )) or 0
        else:  # BDM
            active_load = (await db.scalar(
                select(func.count(OfficeLead.id)).where(
                    OfficeLead.assigned_bdm_id == emp.id,
                    OfficeLead.status == LeadStatus.PENDING_BDM_REVIEW
                )
            )) or 0
            completed = (await db.scalar(
                select(func.count(OfficeLead.id)).where(
                    OfficeLead.assigned_bdm_id == emp.id,
                    OfficeLead.status.in_([LeadStatus.BDM_ACCEPTED, LeadStatus.CONVERTED])
                )
            )) or 0

        total_handled = active_load + completed
        success_rate = round((completed / total_handled * 100.0), 2) if total_handled > 0 else 0.0

        metrics.append(
            StaffEfficiencyItem(
                emp_code=emp.emp_code,
                name=f"{usr.first_name} {usr.last_name}",
                role=usr.role,
                department=emp.department,
                active_load=active_load,
                completed_actions=completed,
                success_rate_pct=success_rate,
            )
        )
    return metrics

# 3. Master Operational Reassignment & Override Handshake
@router.post("/override-reassign", response_model=ReassignmentOverrideResponse)
async def executive_reassignment_override(
    payload: ReassignmentOverridePayload,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(require_roles(EXECUTIVE_ROLES))],
):
    update_vals = {}

    if payload.new_caller_id:
        caller_exists = await db.scalar(select(OfficeEmployee.id).where(OfficeEmployee.id == payload.new_caller_id))
        if not caller_exists:
            raise HTTPException(status_code=400, detail="Target new_caller_id does not exist.")
        update_vals["assigned_caller_id"] = payload.new_caller_id

    if payload.new_bdm_id:
        bdm_exists = await db.scalar(select(OfficeEmployee.id).where(OfficeEmployee.id == payload.new_bdm_id))
        if not bdm_exists:
            raise HTTPException(status_code=400, detail="Target new_bdm_id does not exist.")
        update_vals["assigned_bdm_id"] = payload.new_bdm_id

    if payload.override_status:
        update_vals["status"] = payload.override_status

    if not update_vals:
        raise HTTPException(status_code=400, detail="Must supply at least one field to update.")

    stmt = (
        update(OfficeLead)
        .where(OfficeLead.id.in_(payload.lead_ids))
        .values(**update_vals)
    )
    result = await db.execute(stmt)
    await db.commit()

    # Manual audit record for governance override
    audit_entry = OfficeAuditLog(
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=current_user.role.value,
        method="POST",
        route_path="/api/v1/governance/override-reassign",
        status_code=200,
        latency_ms=0,
        action_description=f"Executive Override on {result.rowcount} leads: {payload.audit_reason}",
        metadata_payload={
            "lead_ids": [str(lid) for lid in payload.lead_ids],
            "updates": {k: str(v) for k, v in update_vals.items()},
            "reason": payload.audit_reason
        }
    )
    db.add(audit_entry)
    await db.commit()

    return ReassignmentOverrideResponse(
        success=True,
        modified_count=result.rowcount,
        message=f"Successfully updated {result.rowcount} accounts under executive directive.",
    )

# 4. Enterprise Audit Log Ledger
@router.get("/audit-logs", response_model=list[AuditLogItem])
async def get_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(require_roles(EXECUTIVE_ROLES))],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    actor_email: str | None = Query(None),
):
    stmt = select(OfficeAuditLog)
    if actor_email:
        stmt = stmt.where(OfficeAuditLog.actor_email.ilike(f"%{actor_email.strip()}%"))

    stmt = stmt.order_by(desc(OfficeAuditLog.created_at)).offset(offset).limit(limit)
    return (await db.execute(stmt)).scalars().all()