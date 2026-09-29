import enum
import uuid
from datetime import datetime, date, time
from sqlalchemy import String, Integer, Numeric, Boolean, Date, Time, DateTime, ForeignKey, Text, Enum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    LATE = "LATE"
    HALF_DAY = "HALF_DAY"
    ABSENT = "ABSENT"

class LeaveType(str, enum.Enum):
    CASUAL = "CASUAL"
    SICK = "SICK"
    PAID = "PAID"
    UNPAID = "UNPAID"

class LeaveStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

class OfficeCompensation(Base):
    __tablename__ = "office_compensations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("office_employees.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    base_salary: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    hra: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    special_allowance: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    bank_account_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bank_ifsc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pan_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    employee = relationship("OfficeEmployee")

class OfficeAttendance(Base):
    __tablename__ = "office_attendance"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("office_employees.id", ondelete="CASCADE"), nullable=False, index=True)
    punch_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False, index=True)
    
    clock_in: Mapped[time | None] = mapped_column(Time, nullable=True)
    clock_out: Mapped[time | None] = mapped_column(Time, nullable=True)
    status: Mapped[AttendanceStatus] = mapped_column(Enum(AttendanceStatus), default=AttendanceStatus.PRESENT, nullable=False)
    
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    employee = relationship("OfficeEmployee")

Index("idx_attendance_emp_date", OfficeAttendance.employee_id, OfficeAttendance.punch_date, unique=True)

class OfficeLeave(Base):
    __tablename__ = "office_leaves"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("office_employees.id", ondelete="CASCADE"), nullable=False, index=True)
    
    leave_type: Mapped[LeaveType] = mapped_column(Enum(LeaveType), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    
    status: Mapped[LeaveStatus] = mapped_column(Enum(LeaveStatus), default=LeaveStatus.PENDING, index=True, nullable=False)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("office_employees.id", ondelete="SET NULL"), nullable=True)
    review_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    employee = relationship("OfficeEmployee", foreign_keys=[employee_id])
    reviewer = relationship("OfficeEmployee", foreign_keys=[reviewed_by_id])