"""Require positive photo dimensions.

Revision ID: 20260820_01
Revises: 20260818_02
Create Date: 2026-08-20

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260820_01"
down_revision: str | None = "20260818_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_photos_dimensions", "photos", type_="check")
    op.alter_column("photos", "width", existing_type=sa.Integer(), nullable=False)
    op.alter_column("photos", "height", existing_type=sa.Integer(), nullable=False)
    op.create_check_constraint("ck_photos_dimensions", "photos", "width > 0 AND height > 0")


def downgrade() -> None:
    op.drop_constraint("ck_photos_dimensions", "photos", type_="check")
    op.alter_column("photos", "height", existing_type=sa.Integer(), nullable=True)
    op.alter_column("photos", "width", existing_type=sa.Integer(), nullable=True)
    op.create_check_constraint(
        "ck_photos_dimensions",
        "photos",
        "(width IS NULL AND height IS NULL) OR (width > 0 AND height > 0)",
    )
