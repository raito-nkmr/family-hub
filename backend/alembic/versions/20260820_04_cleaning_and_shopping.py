"""Create cleaning and shopping schema.

Revision ID: 20260820_04
Revises: 20260820_03
Create Date: 2026-08-20

"""

# Alembic operations are kept explicit so this revision remains independent
# from the evolving SQLAlchemy model definitions.
# ruff: noqa: E501

import sqlalchemy as sa

from alembic import op

revision: str = "20260820_04"
down_revision: str | None = "20260820_03"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "cleaning_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 120", name="ck_cleaning_tasks_name_length"),
        sa.CheckConstraint("interval_days BETWEEN 1 AND 3650", name="ck_cleaning_tasks_interval_days"),
        sa.CheckConstraint("name = btrim(name)", name="ck_cleaning_tasks_name_trimmed"),
        sa.PrimaryKeyConstraint("id", name="pk_cleaning_tasks"),
    )
    op.create_index("ix_cleaning_tasks_group_id_is_active", "cleaning_tasks", ["group_id", "is_active"], unique=False)
    op.create_table(
        "cleaning_completions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("completed_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cleaning_completions"),
    )
    op.create_index(
        "ix_cleaning_completions_task_id_completed_at",
        "cleaning_completions",
        ["task_id", sa.literal_column("completed_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_index(
        "ix_cleaning_completions_completed_by_user_id",
        "cleaning_completions",
        ["completed_by_user_id"],
        unique=False,
    )
    op.create_table(
        "shopping_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("purchased_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(purchased_by_user_id IS NULL AND purchased_at IS NULL) OR (purchased_by_user_id IS NOT NULL AND purchased_at IS NOT NULL)",
            name="ck_shopping_items_purchase_state",
        ),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 120", name="ck_shopping_items_name_length"),
        sa.CheckConstraint("name = btrim(name)", name="ck_shopping_items_name_trimmed"),
        sa.PrimaryKeyConstraint("id", name="pk_shopping_items"),
    )
    op.create_index(
        "ix_shopping_items_group_id_purchase_state",
        "shopping_items",
        ["group_id", "purchased_at", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_shopping_items_created_by_user_id",
        "shopping_items",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_shopping_items_purchased_by_user_id",
        "shopping_items",
        ["purchased_by_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_cleaning_tasks_created_by_user_id_users",
        "cleaning_tasks",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_cleaning_tasks_group_id_family_groups",
        "cleaning_tasks",
        "family_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_shopping_items_created_by_user_id_users",
        "shopping_items",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_shopping_items_group_id_family_groups",
        "shopping_items",
        "family_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_shopping_items_purchased_by_user_id_users",
        "shopping_items",
        "users",
        ["purchased_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_cleaning_completions_completed_by_user_id_users",
        "cleaning_completions",
        "users",
        ["completed_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_cleaning_completions_task_id_cleaning_tasks",
        "cleaning_completions",
        "cleaning_tasks",
        ["task_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_cleaning_completions_task_id_cleaning_tasks", "cleaning_completions", type_="foreignkey")
    op.drop_constraint("fk_cleaning_completions_completed_by_user_id_users", "cleaning_completions", type_="foreignkey")
    op.drop_constraint("fk_shopping_items_purchased_by_user_id_users", "shopping_items", type_="foreignkey")
    op.drop_constraint("fk_shopping_items_group_id_family_groups", "shopping_items", type_="foreignkey")
    op.drop_constraint("fk_shopping_items_created_by_user_id_users", "shopping_items", type_="foreignkey")
    op.drop_constraint("fk_cleaning_tasks_group_id_family_groups", "cleaning_tasks", type_="foreignkey")
    op.drop_constraint("fk_cleaning_tasks_created_by_user_id_users", "cleaning_tasks", type_="foreignkey")
    op.drop_index("ix_cleaning_completions_task_id_completed_at", table_name="cleaning_completions")
    op.drop_index("ix_cleaning_completions_completed_by_user_id", table_name="cleaning_completions")
    op.drop_table("cleaning_completions")
    op.drop_index("ix_shopping_items_purchased_by_user_id", table_name="shopping_items")
    op.drop_index("ix_shopping_items_created_by_user_id", table_name="shopping_items")
    op.drop_index("ix_shopping_items_group_id_purchase_state", table_name="shopping_items")
    op.drop_table("shopping_items")
    op.drop_index("ix_cleaning_tasks_group_id_is_active", table_name="cleaning_tasks")
    op.drop_table("cleaning_tasks")
