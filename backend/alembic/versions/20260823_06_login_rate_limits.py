"""Add shared login rate-limit state.

This revision is schema-only. Login attempt rows are created and removed by the
application's rate limiter and are not seeded or backfilled by the migration.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "20260823_06_login_rate_limits"
down_revision: str | None = "20260822_05_shopping_trip_states"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "login_rate_limits",
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint(
            "key_hash ~ '^[0-9a-f]{64}$'",
            name="ck_login_rate_limits_key_hash_lower_hex",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_login_rate_limits_attempt_count_nonnegative",
        ),
        sa.PrimaryKeyConstraint("key_hash", name="pk_login_rate_limits"),
    )
    op.create_index("ix_login_rate_limits_updated_at", "login_rate_limits", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_login_rate_limits_updated_at", table_name="login_rate_limits")
    op.drop_table("login_rate_limits")
