import uuid
from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.office_auth import OfficeUser, OfficeEmployee, OfficeRole
from app.models.office_lead import OfficeLead, LeadStatus
from app.models.office_operations import (
    OfficeOperationsClearance,
    ComplianceStatus,
    DispatchState,
)
from app.schemas.office_operations import (
    OperationsQueueItem,
    AttestationChecklistPayload,
    DispatchManifestSignOffPayload,
    OperationsClearanceResponse,
    OperationsKpiSummary,
)
from app.dependencies.office_auth import get_current_user, require_roles
from app.services.manifest_pdf_engine import generate_operations_manifest_pdf

router = APIRouter(prefix="/operations", tags=["Office Operations Head & Central Dispatch"])

OPERATIONS_PERMITTED_ROLES = [
    OfficeRole.SUPER_ADMIN,
    OfficeRole.COO,
    OfficeRole.OPERATIONS_HEAD,
]

def get_ops_employee(user: OfficeUser) -> OfficeEmployee:
    if user.role not in OPERATIONS_PERMITTED_ROLES:
        raise HTTPException(status_code=403, detail="Access forbidden: Requires Operations Head or Executive governance scope.")
    if not user.employee_profile:
        raise HTTPException(status_code=400, detail="User lacks an assigned employee hierarchy profile.")
    return user.employee_profile

# 1. Operations Clearance Queue (All BDM_ACCEPTED and OPERATIONS_APPROVED accounts)
@router.get("/queue", response_model=list[OperationsQueueItem])
async def get_operations_clearance_queue(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(require_roles(OPERATIONS_PERMITTED_ROLES))],
):
    stmt = (
        select(OfficeLead, OfficeOperationsClearance)
        .outerjoin(OfficeOperationsClearance, OfficeLead.id == OfficeOperationsClearance.lead_id)
        .where(
            OfficeLead.status.in_([
                LeadStatus.BDM_ACCEPTED,
                LeadStatus.OPERATIONS_APPROVED,
                LeadStatus.CONVERTED,
            ])
        )
        .order_by(desc(OfficeLead.updated_at))
    )
    results = (await db.execute(stmt)).all()

    queue = []
    for lead, clearance in results:
        comp_status = clearance.compliance_status if clearance else ComplianceStatus.PENDING_VERIFICATION
        disp_state = clearance.dispatch_state if clearance else DispatchState.PENDING_CLEARANCE

        queue.append(
            OperationsQueueItem(
                lead_id=lead.id,
                lead_code=lead.lead_code,
                company_name=lead.company_name,
                country=lead.country,
                state=lead.state,
                commercial_model=lead.commercial_model,
                tier=lead.tier,
                score=lead.score,
                status=lead.status,
                volume_estimate=lead.volume_estimate,
                bdm_remarks=lead.bdm_remarks,
                compliance_status=comp_status,
                dispatch_state=disp_state,
                updated_at=lead.updated_at,
            )
        )
    return queue

# 2. Statutory Checklist Attestation
@router.post("/leads/{lead_id}/attestation", response_model=OperationsClearanceResponse)
async def submit_statutory_attestation(
    lead_id: uuid.UUID,
    payload: AttestationChecklistPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(require_roles(OPERATIONS_PERMITTED_ROLES))],
):
    emp = get_ops_employee(current_user)

    lead = await db.scalar(select(OfficeLead).where(OfficeLead.id == lead_id))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead record not found.")

    clearance = await db.scalar(select(OfficeOperationsClearance).where(OfficeOperationsClearance.lead_id == lead.id))
    if not clearance:
        clearance = OfficeOperationsClearance(lead_id=lead.id, operations_head_id=emp.id)
        db.add(clearance)

    clearance.excise_license_verified = payload.excise_license_verified
    clearance.excise_license_no = payload.excise_license_no
    clearance.license_expiry_date = payload.license_expiry_date
    clearance.coo_msds_cleared = payload.coo_msds_cleared
    clearance.bonded_warehouse_verified = payload.bonded_warehouse_verified
    clearance.territory_exclusivity_cleared = payload.territory_exclusivity_cleared
    clearance.operations_head_id = emp.id

    # Determine Compliance State
    all_cleared = (
        payload.excise_license_verified
        and payload.coo_msds_cleared
        and payload.bonded_warehouse_verified
        and payload.territory_exclusivity_cleared
    )
    clearance.compliance_status = ComplianceStatus.COMPLIANT if all_cleared else ComplianceStatus.NON_COMPLIANT

    if payload.notes:
        clearance.clearance_notes = f"[COMPLIANCE AUDIT]: {payload.notes.strip()}"

    await db.commit()
    await db.refresh(clearance)
    return clearance

# 3. Dispatch Manifest Authorization & Account Conversion
@router.post("/leads/{lead_id}/authorize-dispatch", response_model=OperationsClearanceResponse)
async def authorize_dispatch_and_convert(
    lead_id: uuid.UUID,
    payload: DispatchManifestSignOffPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(require_roles(OPERATIONS_PERMITTED_ROLES))],
):
    emp = get_ops_employee(current_user)

    lead = await db.scalar(select(OfficeLead).where(OfficeLead.id == lead_id))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead record not found.")

    clearance = await db.scalar(select(OfficeOperationsClearance).where(OfficeOperationsClearance.lead_id == lead.id))
    if not clearance or clearance.compliance_status != ComplianceStatus.COMPLIANT:
        raise HTTPException(
            status_code=400,
            detail="Cannot authorize dispatch! Statutory attestation checklist must be COMPLIANT first.",
        )

    # Check for duplicate permit numbers across existing clearances
    existing_permit = await db.scalar(
        select(OfficeOperationsClearance.id).where(
            OfficeOperationsClearance.dispatch_permit_no == payload.dispatch_permit_no.strip(),
            OfficeOperationsClearance.id != clearance.id,
        )
    )
    if existing_permit:
        raise HTTPException(status_code=409, detail="A dispatch permit with this reference number has already been utilized.")

    # Freeze Commercial and Manifest Parameters
    clearance.dispatch_permit_no = payload.dispatch_permit_no.strip()
    clearance.transporter_carrier = payload.transporter_carrier.strip()
    clearance.vehicle_container_no = payload.vehicle_container_no.strip()
    clearance.customs_seal_no = payload.customs_seal_no.strip() if payload.customs_seal_no else None
    clearance.estimated_dispatch_date = payload.estimated_dispatch_date
    clearance.locked_margin_pct = payload.locked_margin_pct
    clearance.locked_annual_cases = payload.locked_annual_cases
    clearance.clearance_notes = payload.clearance_notes.strip()
    clearance.dispatch_state = DispatchState.CLEARED_FOR_DISPATCH
    clearance.cleared_at = datetime.now(timezone.utc).replace(tzinfo=None)
    clearance.operations_head_id = emp.id

    # Transition Lead to CONVERTED
    lead.status = LeadStatus.CONVERTED
    lead.bdm_remarks = (
        f"{lead.bdm_remarks or ''} | [DISPATCH AUTHORIZED by {emp.emp_code}]: "
        f"Permit #{payload.dispatch_permit_no.strip()} | Carrier: {payload.transporter_carrier.strip()} | "
        f"Locked Margin: {payload.locked_margin_pct}%"
    ).strip()

    await db.commit()
    await db.refresh(clearance)
    return clearance

# 4. Generate Official Dispatch Manifest PDF
@router.get("/leads/{lead_id}/download-manifest-pdf")
async def download_dispatch_manifest_pdf(
    lead_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(require_roles(OPERATIONS_PERMITTED_ROLES))],
):
    lead = await db.scalar(select(OfficeLead).where(OfficeLead.id == lead_id))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead record not found.")

    clearance = await db.scalar(select(OfficeOperationsClearance).where(OfficeOperationsClearance.lead_id == lead.id))
    if not clearance or clearance.dispatch_state != DispatchState.CLEARED_FOR_DISPATCH:
        raise HTTPException(
            status_code=400,
            detail="Dispatch manifest can only be generated for accounts in CLEARED_FOR_DISPATCH status.",
        )

    pdf_bytes = generate_operations_manifest_pdf(lead, clearance)
    filename = f"Dispatch_Manifest_{clearance.dispatch_permit_no or lead.lead_code}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

# 5. Operations KPI HUD Summary
@router.get("/kpis", response_model=OperationsKpiSummary)
async def get_operations_kpi_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(require_roles(OPERATIONS_PERMITTED_ROLES))],
):
    # Pending compliance audit
    pending_stmt = select(func.count(OfficeLead.id)).where(
        OfficeLead.status == LeadStatus.BDM_ACCEPTED,
    )
    pending_audit = (await db.scalar(pending_stmt)) or 0

    # Cleared ready for dispatch
    cleared_stmt = select(func.count(OfficeOperationsClearance.id)).where(
        OfficeOperationsClearance.dispatch_state == DispatchState.CLEARED_FOR_DISPATCH,
    )
    cleared_count = (await db.scalar(cleared_stmt)) or 0

    # Converted accounts
    converted_stmt = select(func.count(OfficeLead.id)).where(
        OfficeLead.status == LeadStatus.CONVERTED,
    )
    converted_count = (await db.scalar(converted_stmt)) or 0

    # Holds
    holds_stmt = select(func.count(OfficeOperationsClearance.id)).where(
        OfficeOperationsClearance.dispatch_state == DispatchState.HOLD,
    )
    active_holds = (await db.scalar(holds_stmt)) or 0

    return OperationsKpiSummary(
        pending_compliance_audit=pending_audit,
        cleared_ready_for_dispatch=cleared_count,
        converted_accounts=converted_count,
        active_holds=active_holds,
    )