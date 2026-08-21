"""Add cleaning report settings and immutable completion snapshots.

Revision ID: 20260821_05_cleaning_reports
Revises: 20260821_04_cleaning_categories
Create Date: 2026-08-21

"""

# Alembic operations are kept explicit so this revision remains independent
# from the evolving SQLAlchemy model definitions.
# ruff: noqa: E501

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_05_cleaning_reports"
down_revision: str | None = "20260821_04_cleaning_categories"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "family_groups",
        sa.Column("timezone", sa.String(length=64), server_default=sa.text("'Asia/Tokyo'"), nullable=False),
    )
    op.create_check_constraint(
        "ck_family_groups_timezone_trimmed",
        "family_groups",
        "timezone = btrim(timezone)",
    )
    op.create_check_constraint(
        "ck_family_groups_timezone_length",
        "family_groups",
        "char_length(timezone) BETWEEN 1 AND 64",
    )

    op.add_column("cleaning_completions", sa.Column("task_name_snapshot", sa.String(length=120), nullable=False))
    op.add_column("cleaning_completions", sa.Column("category_id", sa.UUID(), nullable=True))
    op.add_column("cleaning_completions", sa.Column("category_name_snapshot", sa.String(length=40), nullable=False))
    op.create_check_constraint(
        "ck_cleaning_completions_task_name_trimmed",
        "cleaning_completions",
        "task_name_snapshot = btrim(task_name_snapshot)",
    )
    op.create_check_constraint(
        "ck_cleaning_completions_task_name_length",
        "cleaning_completions",
        "char_length(task_name_snapshot) BETWEEN 1 AND 120",
    )
    op.create_check_constraint(
        "ck_cleaning_completions_category_name_trimmed",
        "cleaning_completions",
        "category_name_snapshot = btrim(category_name_snapshot)",
    )
    op.create_check_constraint(
        "ck_cleaning_completions_category_name_length",
        "cleaning_completions",
        "char_length(category_name_snapshot) BETWEEN 1 AND 40",
    )
    op.create_index(
        "ix_cleaning_completions_completed_at_task_id",
        "cleaning_completions",
        ["completed_at", "task_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_cleaning_completions_category_id_cleaning_categories",
        "cleaning_completions",
        "cleaning_categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_cleaning_completions_category_id_cleaning_categories",
        "cleaning_completions",
        type_="foreignkey",
    )
    op.drop_index("ix_cleaning_completions_completed_at_task_id", table_name="cleaning_completions")
    op.drop_constraint(
        "ck_cleaning_completions_category_name_length",
        "cleaning_completions",
        type_="check",
    )
    op.drop_constraint(
        "ck_cleaning_completions_category_name_trimmed",
        "cleaning_completions",
        type_="check",
    )
    op.drop_constraint(
        "ck_cleaning_completions_task_name_length",
        "cleaning_completions",
        type_="check",
    )
    op.drop_constraint(
        "ck_cleaning_completions_task_name_trimmed",
        "cleaning_completions",
        type_="check",
    )
    op.drop_column("cleaning_completions", "category_name_snapshot")
    op.drop_column("cleaning_completions", "category_id")
    op.drop_column("cleaning_completions", "task_name_snapshot")

    op.drop_constraint("ck_family_groups_timezone_length", "family_groups", type_="check")
    op.drop_constraint("ck_family_groups_timezone_trimmed", "family_groups", type_="check")
    op.drop_column("family_groups", "timezone")
