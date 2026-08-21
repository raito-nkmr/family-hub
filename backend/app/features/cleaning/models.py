from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CleaningCategory(Base):
    __tablename__ = "cleaning_categories"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_cleaning_categories"),
        CheckConstraint("name = btrim(name)", name="ck_cleaning_categories_name_trimmed"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 40", name="ck_cleaning_categories_name_length"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    group_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("family_groups.id", ondelete="CASCADE", name="fk_cleaning_categories_group_id_family_groups"),
    )
    name: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class CleaningTask(Base):
    __tablename__ = "cleaning_tasks"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_cleaning_tasks"),
        CheckConstraint("name = btrim(name)", name="ck_cleaning_tasks_name_trimmed"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 120", name="ck_cleaning_tasks_name_length"),
        CheckConstraint("interval_days BETWEEN 1 AND 3650", name="ck_cleaning_tasks_interval_days"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    group_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("family_groups.id", ondelete="CASCADE", name="fk_cleaning_tasks_group_id_family_groups"),
    )
    name: Mapped[str] = mapped_column(String(120))
    category_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "cleaning_categories.id",
            ondelete="RESTRICT",
            name="fk_cleaning_tasks_category_id_cleaning_categories",
        ),
    )
    interval_days: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_by_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_cleaning_tasks_created_by_user_id_users"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class CleaningCompletion(Base):
    __tablename__ = "cleaning_completions"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_cleaning_completions"),
        CheckConstraint(
            "task_name_snapshot = btrim(task_name_snapshot)",
            name="ck_cleaning_completions_task_name_trimmed",
        ),
        CheckConstraint(
            "char_length(task_name_snapshot) BETWEEN 1 AND 120",
            name="ck_cleaning_completions_task_name_length",
        ),
        CheckConstraint(
            "category_name_snapshot = btrim(category_name_snapshot)",
            name="ck_cleaning_completions_category_name_trimmed",
        ),
        CheckConstraint(
            "char_length(category_name_snapshot) BETWEEN 1 AND 40",
            name="ck_cleaning_completions_category_name_length",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("cleaning_tasks.id", ondelete="CASCADE", name="fk_cleaning_completions_task_id_cleaning_tasks"),
    )
    task_name_snapshot: Mapped[str] = mapped_column(String(120))
    category_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "cleaning_categories.id",
            ondelete="SET NULL",
            name="fk_cleaning_completions_category_id_cleaning_categories",
        ),
    )
    category_name_snapshot: Mapped[str] = mapped_column(String(40))
    completed_by_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_cleaning_completions_completed_by_user_id_users"),
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


Index("ix_cleaning_categories_group_id", CleaningCategory.group_id)
Index(
    "uq_cleaning_categories_group_name_ci",
    CleaningCategory.group_id,
    func.lower(CleaningCategory.name),
    unique=True,
)
Index("ix_cleaning_tasks_group_id_is_active", CleaningTask.group_id, CleaningTask.is_active)
Index("ix_cleaning_tasks_category_id", CleaningTask.category_id)
Index(
    "ix_cleaning_completions_task_id_completed_at",
    CleaningCompletion.task_id,
    CleaningCompletion.completed_at.desc(),
    CleaningCompletion.id.desc(),
)
Index("ix_cleaning_completions_completed_at_task_id", CleaningCompletion.completed_at, CleaningCompletion.task_id)
Index("ix_cleaning_completions_completed_by_user_id", CleaningCompletion.completed_by_user_id)
