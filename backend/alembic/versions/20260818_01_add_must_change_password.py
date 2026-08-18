"""Add the forced password-change state for operator resets.

Revision ID: 20260818_01
Revises: 20260715_01
Create Date: 2026-08-18

"""

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_01"
down_revision: str | None = "20260715_01"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
