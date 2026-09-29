from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict
from app.models.office_auth import OfficeRole

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class EmployeeContext(BaseModel):
    emp_code: str
    department: str
    designation: str
    reporting_to_id: UUID | None = None
    is_field_staff: bool

    model_config = ConfigDict(from_attributes=True)

class UserAuthResponse(BaseModel):
    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    role: OfficeRole
    state_code: str | None = None
    is_active: bool
    employee_profile: EmployeeContext | None = None

    model_config = ConfigDict(from_attributes=True)

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str