from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, PrimaryKeyConstraint, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MaintenanceJobType(StrEnum):
    PHOTO_INTEGRITY = "photo_integrity"
    DATABASE_BACKUP = "database_backup"
    SECONDARY_STORAGE_BACKUP = "secondary_storage_backup"
    TRASH_PURGE = "trash_purge"
    RESTORE_DRILL = "restore_drill"


class MaintenanceRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    WARNING = "warning"
    FAILED = "failed"


class MaintenanceRun(Base):
    __tablename__ = "maintenance_runs"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_maintenance_runs"),
        CheckConstraint(
            "job_type IN ('photo_integrity', 'database_backup', 'secondary_storage_backup', "
            "'trash_purge', 'restore_drill')",
            name="ck_maintenance_runs_job_type",
        ),
        CheckConstraint(
            "status IN ('running', 'succeeded', 'warning', 'failed')",
            name="ck_maintenance_runs_status",
        ),
        CheckConstraint(
            "(status = 'running' AND finished_at IS NULL) OR (status <> 'running' AND finished_at IS NOT NULL)",
            name="ck_maintenance_runs_finished_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)


Index("ix_maintenance_runs_job_type_started_at", MaintenanceRun.job_type, MaintenanceRun.started_at.desc())
