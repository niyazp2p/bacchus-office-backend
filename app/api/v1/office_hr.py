import uuid
from datetime import datetime, date, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import hash_password
from app.models.office_auth import OfficeUser, OfficeEmployee, OfficeRole
from app.models.office_hr import (
    OfficeCompensation,
    OfficeAttendance,
    OfficeLeave,
    AttendanceStatus,
    LeaveStatus,
)
from app.schemas.office_hr import (
    EmployeeCreate,
    EmployeeUpdate,
    CompensationUpdate,
    EmployeeDetailResponse,
    CompensationResponse,
    ClockInOutRequest,
    AttendanceResponse,
    LeaveApplyRequest,
    LeaveReviewRequest,
    LeaveResponse,
)
from app.dependencies.office_auth import get_current_user, require_roles

router = APIRouter(prefix="/hr", tags=["Office HR & Employee Management"])

HR_PERMITTED_ROLES = [OfficeRole.SUPER_ADMIN, OfficeRole.COO, OfficeRole.HR_MANAGER]

# 1. Provision New Employee & Credentials (Atomic Handshake)
@router.post("/employees", response_model=EmployeeDetailResponse, status_code=status.HTTP_201_CREATED)
async def provision_employee(
    payload: EmployeeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(require_roles(HR_PERMITTED_ROLES))],
):
    # Check duplicate email or emp_code
    existing_user = await db.scalar(select(OfficeUser.id).where(OfficeUser.email == payload.email.strip().lower()))
    if existing_user:
        raise HTTPException(status_code=409, detail="A user with this email address already exists.")

    existing_code = await db.scalar(select(OfficeEmployee.id).where(OfficeEmployee.emp_code == payload.emp_code.strip().upper()))
    if existing_code:
        raise HTTPException(status_code=409, detail="An employee with this Employee Code already exists.")

    # Validate reporting manager exists if provided
    if payload.reporting_to_id:
        manager_exists = await db.scalar(select(OfficeEmployee.id).where(OfficeEmployee.id == payload.reporting_to_id))
        if not manager_exists:
            raise HTTPException(status_code=400, detail="Mapped reporting manager (reporting_to_id) does not exist.")

    # Create User
    new_user = OfficeUser(
        email=payload.email.strip().lower(),
        password_hash=hash_password(payload.password),
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        role=payload.role,
        state_code=payload.state_code.strip().upper() if payload.state_code else "DL",
    )
    db.add(new_user)
    await db.flush()

    # Create Employee Dossier
    new_emp = OfficeEmployee(
        user_id=new_user.id,
        emp_code=payload.emp_code.strip().upper(),
        department=payload.department.strip().upper(),
        designation=payload.designation.strip(),
        reporting_to_id=payload.reporting_to_id,
    )
    db.add(new_emp)
    await db.flush()

    # Create Compensation record if specified
    comp_obj = None
    if payload.base_salary is not None:
        comp_obj = OfficeCompensation(
            employee_id=new_emp.id,
            base_salary=payload.base_salary,
            hra=payload.hra or 0.0,
            special_allowance=payload.special_allowance or 0.0,
            bank_account_number=payload.bank_account_number,
            bank_ifsc=payload.bank_ifsc,
            pan_number=payload.pan_number,
        )
        db.add(comp_obj)

    await db.commit()

    return EmployeeDetailResponse(
        id=new_emp.id,
        user_id=new_user.id,
        emp_code=new_emp.emp_code,
        first_name=new_user.first_name,
        last_name=new_user.last_name,
        email=new_user.email,
        role=new_user.role,
        department=new_emp.department,
        designation=new_emp.designation,
        reporting_to_id=new_emp.reporting_to_id,
        is_active=new_user.is_active,
        is_locked=new_user.is_locked,
        compensation=CompensationResponse.model_validate(comp_obj) if comp_obj else None,
        created_at=new_user.created_at,
    )

# 2. List All Employees (Filtered Scoping)
@router.get("/employees", response_model=list[EmployeeDetailResponse])
async def list_employees(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(get_current_user)],
    department: str | None = Query(None),
    role: OfficeRole | None = Query(None),
):
    stmt = (
        select(OfficeEmployee, OfficeUser, OfficeCompensation)
        .join(OfficeUser, OfficeEmployee.user_id == OfficeUser.id)
        .outerjoin(OfficeCompensation, OfficeEmployee.id == OfficeCompensation.employee_id)
    )

    if department:
        stmt = stmt.where(OfficeEmployee.department == department.strip().upper())
    if role:
        stmt = stmt.where(OfficeUser.role == role)

    records = (await db.execute(stmt)).all()
    results = []
    is_hr = current_user.role in HR_PERMITTED_ROLES

    for emp, usr, comp in records:
        results.append(
            EmployeeDetailResponse(
                id=emp.id,
                user_id=usr.id,
                emp_code=emp.emp_code,
                first_name=usr.first_name,
                last_name=usr.last_name,
                email=usr.email,
                role=usr.role,
                department=emp.department,
                designation=emp.designation,
                reporting_to_id=emp.reporting_to_id,
                is_active=usr.is_active,
                is_locked=usr.is_locked,
                compensation=CompensationResponse.model_validate(comp) if (comp and is_hr) else None,
                created_at=usr.created_at,
            )
        )
    return results

# 3. Update Employee Profile & Organizational Linkage
@router.patch("/employees/{employee_id}", response_model=EmployeeDetailResponse)
async def update_employee(
    employee_id: uuid.UUID,
    payload: EmployeeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(require_roles(HR_PERMITTED_ROLES))],
):
    emp = await db.scalar(select(OfficeEmployee).where(OfficeEmployee.id == employee_id))
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found.")

    usr = await db.scalar(select(OfficeUser).where(OfficeUser.id == emp.user_id))
    comp = await db.scalar(select(OfficeCompensation).where(OfficeCompensation.employee_id == emp.id))

    if payload.first_name is not None:
        usr.first_name = payload.first_name.strip()
    if payload.last_name is not None:
        usr.last_name = payload.last_name.strip()
    if payload.department is not None:
        emp.department = payload.department.strip().upper()
    if payload.designation is not None:
        emp.designation = payload.designation.strip()
    if payload.reporting_to_id is not None:
        if payload.reporting_to_id == emp.id:
            raise HTTPException(status_code=400, detail="Employee cannot report to themselves.")
        emp.reporting_to_id = payload.reporting_to_id
    if payload.is_active is not None:
        usr.is_active = payload.is_active
    if payload.is_locked is not None:
        usr.is_locked = payload.is_locked

    await db.commit()
    await db.refresh(emp)
    await db.refresh(usr)

    return EmployeeDetailResponse(
        id=emp.id,
        user_id=usr.id,
        emp_code=emp.emp_code,
        first_name=usr.first_name,
        last_name=usr.last_name,
        email=usr.email,
        role=usr.role,
        department=emp.department,
        designation=emp.designation,
        reporting_to_id=emp.reporting_to_id,
        is_active=usr.is_active,
        is_locked=usr.is_locked,
        compensation=CompensationResponse.model_validate(comp) if comp else None,
        created_at=usr.created_at,
    )
# 4. Modify Compensation (Strict HR Privacy Shield)
@router.put("/employees/{employee_id}/compensation", response_model=CompensationResponse)
async def update_compensation(
    employee_id: uuid.UUID,
    payload: CompensationUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(require_roles(HR_PERMITTED_ROLES))],
):
    emp_exists = await db.scalar(select(OfficeEmployee.id).where(OfficeEmployee.id == employee_id))
    if not emp_exists:
        raise HTTPException(status_code=404, detail="Employee not found.")

    comp = await db.scalar(select(OfficeCompensation).where(OfficeCompensation.employee_id == employee_id))
    if not comp:
        comp = OfficeCompensation(employee_id=employee_id, **payload.model_dump())
        db.add(comp)
    else:
        for k, v in payload.model_dump().items():
            setattr(comp, k, v)

    await db.commit()
    await db.refresh(comp)
    return comp

# 5. Punch In / Clock In
@router.post("/attendance/punch-in", response_model=AttendanceResponse)
async def punch_in(
    payload: ClockInOutRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(get_current_user)],
):
    if not current_user.employee_profile:
        raise HTTPException(status_code=400, detail="User does not have an active employee profile.")

    today = date.today()
    existing = await db.scalar(
        select(OfficeAttendance).where(
            OfficeAttendance.employee_id == current_user.employee_profile.id,
            OfficeAttendance.punch_date == today,
        )
    )
    now_time = datetime.now(timezone.utc).time()

    if existing:
        if existing.clock_in:
            raise HTTPException(status_code=400, detail="Already clocked in for today.")
        existing.clock_in = now_time
        existing.notes = payload.notes
        attendance = existing
    else:
        # Determine status (after 10:00 AM considered LATE)
        att_status = AttendanceStatus.LATE if now_time.hour >= 10 else AttendanceStatus.PRESENT
        attendance = OfficeAttendance(
            employee_id=current_user.employee_profile.id,
            punch_date=today,
            clock_in=now_time,
            status=att_status,
            notes=payload.notes,
            ip_address=request.client.host if request.client else None,
        )
        db.add(attendance)

    await db.commit()
    await db.refresh(attendance)
    return attendance

# 6. Punch Out / Clock Out
@router.post("/attendance/punch-out", response_model=AttendanceResponse)
async def punch_out(
    payload: ClockInOutRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(get_current_user)],
):
    if not current_user.employee_profile:
        raise HTTPException(status_code=400, detail="User does not have an active employee profile.")

    today = date.today()
    attendance = await db.scalar(
        select(OfficeAttendance).where(
            OfficeAttendance.employee_id == current_user.employee_profile.id,
            OfficeAttendance.punch_date == today,
        )
    )
    if not attendance or not attendance.clock_in:
        raise HTTPException(status_code=400, detail="Cannot punch out without clocking in first.")

    now_time = datetime.now(timezone.utc).time()
    attendance.clock_out = now_time
    if payload.notes:
        attendance.notes = f"{attendance.notes or ''} | Out: {payload.notes}".strip()

    await db.commit()
    await db.refresh(attendance)
    return attendance

# 7. Apply for Leave
@router.post("/leaves", response_model=LeaveResponse, status_code=status.HTTP_201_CREATED)
async def apply_leave(
    payload: LeaveApplyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(get_current_user)],
):
    if not current_user.employee_profile:
        raise HTTPException(status_code=400, detail="User does not have an active employee profile.")

    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="End date cannot be prior to start date.")

    leave_record = OfficeLeave(
        employee_id=current_user.employee_profile.id,
        leave_type=payload.leave_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason.strip(),
        status=LeaveStatus.PENDING,
    )
    db.add(leave_record)
    await db.commit()
    await db.refresh(leave_record)
    return leave_record

# 8. Review Leave Application (HR or Reporting Manager)
@router.patch("/leaves/{leave_id}/review", response_model=LeaveResponse)
async def review_leave(
    leave_id: uuid.UUID,
    payload: LeaveReviewRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(get_current_user)],
):
    leave = await db.scalar(select(OfficeLeave).where(OfficeLeave.id == leave_id))
    if not leave:
        raise HTTPException(status_code=404, detail="Leave record not found.")

    is_hr = current_user.role in HR_PERMITTED_ROLES
    is_manager = (
        current_user.employee_profile
        and await db.scalar(
            select(OfficeEmployee.id).where(
                OfficeEmployee.id == leave.employee_id,
                OfficeEmployee.reporting_to_id == current_user.employee_profile.id,
            )
        )
    )

    if not is_hr and not is_manager:
        raise HTTPException(status_code=403, detail="Unauthorized: Only HR or direct reporting managers can review leaves.")

    leave.status = payload.status
    leave.review_remarks = payload.remarks
    if current_user.employee_profile:
        leave.reviewed_by_id = current_user.employee_profile.id

    await db.commit()
    await db.refresh(leave)
    return leave

@router.delete(
    "/employees/{employee_id}",
    status_code=status.HTTP_200_OK,
    summary="Expunge Employee & Credentials",
)
async def delete_employee(
    employee_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[OfficeUser, Depends(require_roles(HR_PERMITTED_ROLES))],
):
    # 1. Fetch employee node
    emp = await db.scalar(
        select(OfficeEmployee).where(OfficeEmployee.id == employee_id)
    )
    if not emp:
        raise HTTPException(status_code=404, detail="Employee dossier not found.")

    # Guard: Prevent deleting self
    if current_user.employee_profile and current_user.employee_profile.id == emp.id:
        raise HTTPException(
            status_code=400,
            detail="Forbidden: Administrative users cannot delete their own profile.",
        )

    # 2. Detach any subordinate direct-reports (set reporting_to_id to NULL)
    subordinates = (
        await db.execute(
            select(OfficeEmployee).where(OfficeEmployee.reporting_to_id == emp.id)
        )
    ).scalars().all()
    for sub in subordinates:
        sub.reporting_to_id = None

    # 3. Retrieve linked OfficeUser account
    user_to_delete = await db.scalar(
        select(OfficeUser).where(OfficeUser.id == emp.user_id)
    )

    emp_code = emp.emp_code
    full_name = (
        f"{user_to_delete.first_name} {user_to_delete.last_name}"
        if user_to_delete
        else "Unknown"
    )

    # 4. Expunge employee dossier (DB cascades handle compensations, attendance, and leaves)
    await db.delete(emp)

    # 5. Expunge linked user credentials & active sessions
    if user_to_delete:
        await db.delete(user_to_delete)

    await db.commit()

    return {
        "status": "success",
        "message": f"Employee {full_name} ({emp_code}) and associated credentials expunged from the system.",
        "employee_id": str(employee_id),
    }