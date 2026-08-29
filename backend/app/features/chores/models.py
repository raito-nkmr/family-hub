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


class ChoreCategory(Base):
    __tablename__ = "chore_categories"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_chore_categories"),
        CheckConstraint("name = btrim(name)", name="ck_chore_categories_name_trimmed"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 40", name="ck_chore_categories_name_length"),
        CheckConstraint("sort_order >= 0", name="ck_chore_categories_sort_order"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    group_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("family_groups.id", ondelete="CASCADE", name="fk_chore_categories_group_id_family_groups"),
    )
    name: Mapped[str] = mapped_column(String(40))
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class ChoreTask(Base):
    __tablename__ = "chore_tasks"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_chore_tasks"),
        CheckConstraint("task_name = btrim(task_name)", name="ck_chore_tasks_task_name_trimmed"),
        CheckConstraint("char_length(task_name) BETWEEN 1 AND 120", name="ck_chore_tasks_task_name_length"),
        CheckConstraint("interval_days BETWEEN 1 AND 3650", name="ck_chore_tasks_interval_days"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    group_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("family_groups.id", ondelete="CASCADE", name="fk_chore_tasks_group_id_family_groups"),
    )
    task_name: Mapped[str] = mapped_column(String(120))
    category_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "chore_categories.id",
            ondelete="RESTRICT",
            name="fk_chore_tasks_category_id_chore_categories",
        ),
    )
    interval_days: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_by_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_chore_tasks_created_by_user_id_users"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class ChoreCompletion(Base):
    __tablename__ = "chore_completions"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_chore_completions"),
        CheckConstraint(
            "task_name_snapshot = btrim(task_name_snapshot)",
            name="ck_chore_completions_task_name_trimmed",
        ),
        CheckConstraint(
            "char_length(task_name_snapshot) BETWEEN 1 AND 120",
            name="ck_chore_completions_task_name_length",
        ),
        CheckConstraint(
            "category_name_snapshot = btrim(category_name_snapshot)",
            name="ck_chore_completions_category_name_trimmed",
        ),
        CheckConstraint(
            "char_length(category_name_snapshot) BETWEEN 1 AND 40",
            name="ck_chore_completions_category_name_length",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("chore_tasks.id", ondelete="CASCADE", name="fk_chore_completions_task_id_chore_tasks"),
    )
    task_name_snapshot: Mapped[str] = mapped_column(String(120))
    category_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "chore_categories.id",
            ondelete="SET NULL",
            name="fk_chore_completions_category_id_chore_categories",
        ),
    )
    category_name_snapshot: Mapped[str] = mapped_column(String(40))
    completed_by_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_chore_completions_completed_by_user_id_users"),
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


Index("ix_chore_categories_group_id", ChoreCategory.group_id)
Index(
    "ix_chore_categories_group_sort_order",
    ChoreCategory.group_id,
    ChoreCategory.sort_order,
    ChoreCategory.id,
)
Index(
    "uq_chore_categories_group_name_ci",
    ChoreCategory.group_id,
    func.lower(ChoreCategory.name),
    unique=True,
)
Index("ix_chore_tasks_group_id_is_active", ChoreTask.group_id, ChoreTask.is_active)
Index("ix_chore_tasks_category_id", ChoreTask.category_id)
Index(
    "ix_chore_completions_task_id_completed_at",
    ChoreCompletion.task_id,
    ChoreCompletion.completed_at.desc(),
    ChoreCompletion.id.desc(),
)
Index("ix_chore_completions_completed_at_task_id", ChoreCompletion.completed_at, ChoreCompletion.task_id)
Index("ix_chore_completions_completed_by_user_id", ChoreCompletion.completed_by_user_id)
