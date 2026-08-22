"""Rename the session last-use timestamp.

Revision ID: 20260822_03_session_last_used
Revises: 20260822_02_invitation_names
Create Date: 2026-08-22

"""

from alembic import op

revision: str = "20260822_03_session_last_used"
down_revision: str | None = "20260822_02_invitation_names"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.alter_column("user_sessions", "last_seen_at", new_column_name="last_used_at")


def downgrade() -> None:
    op.alter_column("user_sessions", "last_used_at", new_column_name="last_seen_at")
