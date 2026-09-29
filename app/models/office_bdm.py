import enum
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, Enum, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class BdmAction(str, enum.Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"

class ContainerSpec(str, enum.Enum):
    FCL_20FT = "FCL_20FT"
    FCL_40FT = "FCL_40FT"
    LCL_TRIAL = "LCL_TRIAL"
    DOMESTIC_TRUCKLOAD = "DOMESTIC_TRUCKLOAD"

class IncoTerms(str, enum.Enum):
    FOB_JNPT = "FOB_JNPT"
    CIF_DESTINATION = "CIF_DESTINATION"
    EX_WORKS_PUNJAB = "EX_WORKS_PUNJAB"
    FOR_DOMESTIC = "FOR_DOMESTIC"

class PaymentTerms(str, enum.Enum):
    ADVANCE_100 = "ADVANCE_100"
    LC_AT_SIGHT = "LC_AT_SIGHT"
    ADVANCE_30_LC_70 = "ADVANCE_30_LC_70"
    NET_30 = "NET_30"
    NET_60 = "NET_60"

class RejectionReason(str, enum.Enum):
    INSUFFICIENT_VOLUME = "INSUFFICIENT_VOLUME"
    NON_COMPLIANT_TERRITORY = "NON_COMPLIANT_TERRITORY"
    FAKE_INQUIRY = "FAKE_INQUIRY"
    UNREALISTIC_CREDIT_TERMS = "UNREALISTIC_CREDIT_TERMS"
    DISTRIBUTOR_CONFLICT = "DISTRIBUTOR_CONFLICT"
    OTHER = "OTHER"

class RecycleDisposition(str, enum.Enum):
    RETURN_TO_TELECALLER = "RETURN_TO_TELECALLER"
    PARK_INDEFINITELY = "PARK_INDEFINITELY"
    MARK_LOST = "MARK_LOST"

class OfficeBdmReview(Base):
    __tablename__ = "office_bdm_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("office_leads.id", ondelete="CASCADE"), nullable=False, index=True)
    bdm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("office_employees.id", ondelete="CASCADE"), nullable=False, index=True)
    
    action: Mapped[BdmAction] = mapped_column(Enum(BdmAction), nullable=False)
    
    # Commercial Terms (Applicable if ACCEPT)
    projected_annual_cases: Mapped[int | None] = mapped_column(Integer, nullable=True)
    container_spec: Mapped[ContainerSpec | None] = mapped_column(Enum(ContainerSpec), nullable=True)
    inco_terms: Mapped[IncoTerms | None] = mapped_column(Enum(IncoTerms), nullable=True)
    payment_terms: Mapped[PaymentTerms | None] = mapped_column(Enum(PaymentTerms), nullable=True)
    estimated_margin_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # Rejection & Recycling Terms (Applicable if REJECT)
    rejection_reason: Mapped[RejectionReason | None] = mapped_column(Enum(RejectionReason), nullable=True)
    recycle_disposition: Mapped[RecycleDisposition | None] = mapped_column(Enum(RecycleDisposition), nullable=True)
    rework_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # General assessment remarks
    remarks: Mapped[str] = mapped_column(Text, nullable=False)
    sla_breached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    lead = relationship("OfficeLead", foreign_keys=[lead_id])
    bdm = relationship("OfficeEmployee", foreign_keys=[bdm_id])

Index("idx_bdm_reviews_lead_date", OfficeBdmReview.lead_id, OfficeBdmReview.created_at)