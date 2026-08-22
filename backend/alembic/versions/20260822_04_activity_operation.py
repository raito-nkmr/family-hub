"""Clarify the photo activity grouping identifier.

Revision ID: 20260822_04_activity_operation
Revises: 20260822_03_session_last_used
Create Date: 2026-08-22

"""

from alembic import op

revision: str = "20260822_04_activity_operation"
down_revision: str | None = "20260822_03_session_last_used"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.alter_column("photo_activity_events", "operation_id", new_column_name="activity_operation_id")
    op.execute(
        "ALTER INDEX ix_photo_activity_events_operation_id RENAME TO ix_photo_activity_events_activity_operation_id"
    )


def downgrade() -> None:
    op.execute(
        "ALTER INDEX ix_photo_activity_events_activity_operation_id RENAME TO ix_photo_activity_events_operation_id"
    )
    op.alter_column("photo_activity_events", "activity_operation_id", new_column_name="operation_id")
