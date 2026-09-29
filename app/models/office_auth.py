import enum
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class OfficeRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    COO = "COO"
    HR_MANAGER = "HR_MANAGER"
    OPERATIONS_HEAD = "OPERATIONS_HEAD"
    BDM = "BDM"
    TELECALLER = "TELECALLER"

class OfficeUser(Base):
    __tablename__ = "office_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    role: Mapped[OfficeRole] = mapped_column(Enum(OfficeRole), default=OfficeRole.TELECALLER, nullable=False, index=True)
    state_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    employee_profile = relationship("OfficeEmployee", back_populates="user", uselist=False, cascade="all, delete-orphan")
    sessions = relationship("OfficeUserSession", back_populates="user", cascade="all, delete-orphan")

class OfficeEmployee(Base):
    __tablename__ = "office_employees"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("office_users.id", ondelete="CASCADE"), unique=True, nullable=False)
    emp_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    department: Mapped[str] = mapped_column(String(50), nullable=False)
    designation: Mapped[str] = mapped_column(String(100), nullable=False)
    reporting_to_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("office_employees.id", ondelete="SET NULL"), nullable=True)
    is_field_staff: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    joining_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("OfficeUser", back_populates="employee_profile")
    manager = relationship("OfficeEmployee", remote_side=[id], back_populates="subordinates")
    subordinates = relationship("OfficeEmployee", back_populates="manager")

class OfficeUserSession(Base):
    __tablename__ = "office_user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("office_users.id", ondelete="CASCADE"), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("OfficeUser", back_populates="sessions")