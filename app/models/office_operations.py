import enum
import uuid
from datetime import datetime, date
from sqlalchemy import String, Integer, Float, DateTime, Date, ForeignKey, Text, Enum, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class ComplianceStatus(str, enum.Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"

class DispatchState(str, enum.Enum):
    PENDING_CLEARANCE = "PENDING_CLEARANCE"
    CLEARED_FOR_DISPATCH = "CLEARED_FOR_DISPATCH"
    DISPATCHED = "DISPATCHED"
    HOLD = "HOLD"

class OfficeOperationsClearance(Base):
    __tablename__ = "office_operations_clearances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("office_leads.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    operations_head_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("office_employees.id", ondelete="SET NULL"), nullable=True)

    # Statutory & Regulatory Attestation Checklist
    excise_license_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    excise_license_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    license_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    coo_msds_cleared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bonded_warehouse_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    territory_exclusivity_cleared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    compliance_status: Mapped[ComplianceStatus] = mapped_column(Enum(ComplianceStatus), default=ComplianceStatus.PENDING_VERIFICATION, nullable=False)

    # Dispatch & Consignment Logistics
    dispatch_state: Mapped[DispatchState] = mapped_column(Enum(DispatchState), default=DispatchState.PENDING_CLEARANCE, nullable=False)
    dispatch_permit_no: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    transporter_carrier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vehicle_container_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    customs_seal_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estimated_dispatch_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Margin Lock & Sign-Off Remarks
    locked_margin_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    locked_annual_cases: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clearance_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    lead = relationship("OfficeLead", foreign_keys=[lead_id])
    operations_head = relationship("OfficeEmployee", foreign_keys=[operations_head_id])

Index("idx_ops_compliance_status", OfficeOperationsClearance.compliance_status, OfficeOperationsClearance.dispatch_state)