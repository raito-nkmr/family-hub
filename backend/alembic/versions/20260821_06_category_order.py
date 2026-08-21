"""Add persisted ordering for cleaning categories.

Revision ID: 20260821_06_category_order
Revises: 20260821_05_cleaning_reports
Create Date: 2026-08-21

"""

# Alembic operations are kept explicit so this revision remains independent
# from the evolving SQLAlchemy model definitions.
# ruff: noqa: E501

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_06_category_order"
down_revision: str | None = "20260821_05_cleaning_reports"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "cleaning_categories",
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.create_check_constraint(
        "ck_cleaning_categories_sort_order",
        "cleaning_categories",
        "sort_order >= 0",
    )
    op.create_index(
        "ix_cleaning_categories_group_sort_order",
        "cleaning_categories",
        ["group_id", "sort_order", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_cleaning_categories_group_sort_order", table_name="cleaning_categories")
    op.drop_constraint("ck_cleaning_categories_sort_order", "cleaning_categories", type_="check")
    op.drop_column("cleaning_categories", "sort_order")
