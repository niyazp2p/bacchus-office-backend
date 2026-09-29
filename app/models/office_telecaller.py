# app/models/office_telecaller.py
import enum
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Enum, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class CallDisposition(str, enum.Enum):
    CALL_RECEIVED = "CALL_RECEIVED"          # 1) Call received / Connected
    CALL_DECLINED = "CALL_DECLINED"          # 2) Call declined / Cut
    CALL_WAITING = "CALL_WAITING"            # 3) Call waiting / Ringing
    CALL_AFTER_SOMETIME = "CALL_AFTER_SOMETIME"  # 4) Call after sometime / Callback scheduled


class SentimentRating(str, enum.Enum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    SKEPTICAL = "SKEPTICAL"
    HOSTILE = "HOSTILE"


class OfficeCallRecord(Base):
    __tablename__ = "office_call_records"
    __table_args__ = {"extend_existing": True}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("office_leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    caller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("office_employees.id", ondelete="CASCADE"), nullable=False, index=True
    )

    disposition: Mapped[CallDisposition] = mapped_column(Enum(CallDisposition), nullable=False)
    sentiment: Mapped[SentimentRating] = mapped_column(
        Enum(SentimentRating), default=SentimentRating.NEUTRAL, nullable=False
    )
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_callback_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Document check tracking
    portfolio_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    proposal_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    lead = relationship("OfficeLead", foreign_keys=[lead_id])
    caller = relationship("OfficeEmployee", foreign_keys=[caller_id])


Index("idx_call_records_caller_date", OfficeCallRecord.caller_id, OfficeCallRecord.created_at)