import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class OfficeAuditLog(Base):
    __tablename__ = "office_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("office_users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(50), nullable=True)

    method: Mapped[str] = mapped_column(String(10), nullable=False)
    route_path: Mapped[str] = mapped_column(String(255), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Integer, nullable=False)
    client_ip: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    action_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    actor = relationship("OfficeUser", foreign_keys=[actor_id])

Index("idx_audit_logs_actor_date", OfficeAuditLog.actor_id, OfficeAuditLog.created_at)