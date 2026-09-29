import enum
import uuid
from datetime import datetime
from sqlalchemy import (
    String,
    Integer,
    DateTime,
    ForeignKey,
    Text,
    Enum,
    Index,
    Boolean,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class LeadTier(str, enum.Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"


class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    ROUTED_TO_CALLER = "ROUTED_TO_CALLER"
    CONTACTED = "CONTACTED"
    PENDING_BDM_REVIEW = "PENDING_BDM_REVIEW"
    BDM_ACCEPTED = "BDM_ACCEPTED"
    BDM_REJECTED = "BDM_REJECTED"
    OPERATIONS_APPROVED = "OPERATIONS_APPROVED"
    CONVERTED = "CONVERTED"
    PARKED = "PARKED"
    LOST = "LOST"


class CommercialModel(str, enum.Enum):
    DISTRIBUTION = "DISTRIBUTION"
    PRIVATE_LABEL = "PRIVATE_LABEL"
    STATE_OWNERSHIP = "STATE_OWNERSHIP"


class OfficeLead(Base):
    __tablename__ = "office_leads"
    __table_args__ = {"extend_existing": True}
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lead_code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(
        String(50), index=True, nullable=True
    )
    country: Mapped[str] = mapped_column(
        String(100), default="India", nullable=False
    )
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)

    commercial_model: Mapped[CommercialModel] = mapped_column(
        Enum(CommercialModel), default=CommercialModel.DISTRIBUTION, nullable=False
    )
    volume_estimate: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tier: Mapped[LeadTier] = mapped_column(
        Enum(LeadTier), default=LeadTier.COLD, index=True, nullable=False
    )
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus), default=LeadStatus.NEW, index=True, nullable=False
    )

    # Document Checkbox Tracking & Timestamps
    portfolio_sent: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    portfolio_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    proposal_sent: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    proposal_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    # Audit, routing & operational remarks
    dedup_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    caller_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    bdm_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    loss_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Assignments
    assigned_caller_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("office_employees.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_bdm_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("office_employees.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    assigned_caller = relationship(
        "OfficeEmployee", foreign_keys=[assigned_caller_id]
    )
    assigned_bdm = relationship(
        "OfficeEmployee", foreign_keys=[assigned_bdm_id]
    )


Index(
    "idx_office_leads_lookup",
    OfficeLead.status,
    OfficeLead.tier,
    OfficeLead.assigned_caller_id,
)