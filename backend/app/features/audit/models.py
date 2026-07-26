from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Index, PrimaryKeyConstraint, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AdministrativeAuditEvent(Base):
    __tablename__ = "administrative_audit_events"
    __table_args__ = (PrimaryKeyConstraint("id", name="pk_administrative_audit_events"),)

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    scope: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(64))
    actor_user_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    actor_username: Mapped[str] = mapped_column(String(64))
    group_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str] = mapped_column(String(128))
    details: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


Index(
    "ix_administrative_audit_events_created_at_id",
    AdministrativeAuditEvent.created_at.desc(),
    AdministrativeAuditEvent.id.desc(),
)
Index(
    "ix_administrative_audit_events_group_id_created_at",
    AdministrativeAuditEvent.group_id,
    AdministrativeAuditEvent.created_at.desc(),
)
