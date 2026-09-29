from datetime import date, time, datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict, Field
from app.models.office_auth import OfficeRole
from app.models.office_hr import AttendanceStatus, LeaveType, LeaveStatus

class EmployeeCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: OfficeRole
    emp_code: str = Field(..., min_length=3, max_length=50)
    department: str = Field(..., min_length=2, max_length=100)
    designation: str = Field(..., min_length=2, max_length=100)
    state_code: str | None = Field("DL", max_length=10)
    reporting_to_id: UUID | None = None
    
    # Optional initial compensation (Restricted to HR)
    base_salary: float | None = Field(None, ge=0)
    hra: float | None = Field(0.0, ge=0)
    special_allowance: float | None = Field(0.0, ge=0)
    bank_account_number: str | None = None
    bank_ifsc: str | None = None
    pan_number: str | None = None

class EmployeeUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    department: str | None = None
    designation: str | None = None
    reporting_to_id: UUID | None = None
    is_active: bool | None = None
    is_locked: bool | None = None

class CompensationUpdate(BaseModel):
    base_salary: float = Field(..., ge=0)
    hra: float = Field(0.0, ge=0)
    special_allowance: float = Field(0.0, ge=0)
    bank_account_number: str | None = None
    bank_ifsc: str | None = None
    pan_number: str | None = None

class CompensationResponse(BaseModel):
    base_salary: float
    hra: float
    special_allowance: float
    bank_account_number: str | None
    bank_ifsc: str | None
    pan_number: str | None

    model_config = ConfigDict(from_attributes=True)

class EmployeeDetailResponse(BaseModel):
    id: UUID
    user_id: UUID
    emp_code: str
    first_name: str
    last_name: str
    email: EmailStr
    role: OfficeRole
    department: str
    designation: str
    reporting_to_id: UUID | None
    is_active: bool
    is_locked: bool
    compensation: CompensationResponse | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

class ClockInOutRequest(BaseModel):
    notes: str | None = None

class AttendanceResponse(BaseModel):
    id: UUID
    employee_id: UUID
    punch_date: date
    clock_in: time | None
    clock_out: time | None
    status: AttendanceStatus
    notes: str | None

    model_config = ConfigDict(from_attributes=True)

class LeaveApplyRequest(BaseModel):
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: str = Field(..., min_length=5, max_length=1000)

class LeaveReviewRequest(BaseModel):
    status: LeaveStatus
    remarks: str | None = None

class LeaveResponse(BaseModel):
    id: UUID
    employee_id: UUID
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: str
    status: LeaveStatus
    reviewed_by_id: UUID | None
    review_remarks: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)