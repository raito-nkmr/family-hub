"""Add discarded state to shopping trips.

This revision is schema-only. Existing trips are intentionally left unchanged;
legacy cleanup is performed through the shopping history workflow.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "20260822_05_shopping_trip_states"
down_revision: str | None = "20260822_04_shopping_workflow"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("shopping_trips", sa.Column("discarded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shopping_trips", sa.Column("discarded_by_user_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_shopping_trips_discarded_by_user_id_users",
        "shopping_trips",
        "users",
        ["discarded_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_shopping_trips_discard_state",
        "shopping_trips",
        "(discarded_at IS NULL AND discarded_by_user_id IS NULL) OR "
        "(discarded_at IS NOT NULL AND discarded_by_user_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_shopping_trips_discard_not_finalized",
        "shopping_trips",
        "discarded_at IS NULL OR finalized_at IS NULL",
    )
    op.create_index(
        "ix_shopping_trips_discarded_by_user_id",
        "shopping_trips",
        ["discarded_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_shopping_trips_discarded_by_user_id", table_name="shopping_trips")
    op.drop_constraint("ck_shopping_trips_discard_not_finalized", "shopping_trips", type_="check")
    op.drop_constraint("ck_shopping_trips_discard_state", "shopping_trips", type_="check")
    op.drop_constraint("fk_shopping_trips_discarded_by_user_id_users", "shopping_trips", type_="foreignkey")
    op.drop_column("shopping_trips", "discarded_by_user_id")
    op.drop_column("shopping_trips", "discarded_at")
