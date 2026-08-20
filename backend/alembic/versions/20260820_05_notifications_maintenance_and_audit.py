"""Create notification, maintenance, and audit schema.

Revision ID: 20260820_05
Revises: 20260820_04
Create Date: 2026-08-20

"""

# Alembic operations are kept explicit so this revision remains independent
# from the evolving SQLAlchemy model definitions.
# ruff: noqa: E501

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260820_05"
down_revision: str | None = "20260820_04"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("recipient_user_id", sa.UUID(), nullable=False),
        sa.Column("notification_type", sa.String(length=32), nullable=False),
        sa.Column("deduplication_key", sa.String(length=160), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claim_token", sa.UUID(), nullable=True),
        sa.Column("last_error", sa.String(length=128), nullable=True),
        sa.CheckConstraint(
            "notification_type IN ('photo_shared', 'cleaning_due', 'shopping_added')",
            name="ck_notification_outbox_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'sent', 'failed')", name="ck_notification_outbox_status"
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND processed_at IS NULL AND claimed_at IS NULL AND claim_token IS NULL) OR "
            "(status = 'processing' AND processed_at IS NULL AND claimed_at IS NOT NULL AND claim_token IS NOT NULL) OR "
            "(status IN ('sent', 'failed') AND processed_at IS NOT NULL AND claimed_at IS NULL AND claim_token IS NULL)",
            name="ck_notification_outbox_lifecycle_fields",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_notification_outbox_attempt_count"),
        sa.PrimaryKeyConstraint("id", name="pk_notification_outbox"),
        sa.UniqueConstraint("recipient_user_id", "deduplication_key", name="uq_notification_outbox_recipient_dedupe"),
    )
    op.create_index(
        "ix_notification_outbox_pending",
        "notification_outbox",
        ["available_at"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("notification_type", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint(
            "notification_type IN ('photo_shared', 'cleaning_due', 'shopping_added')",
            name="ck_notification_preferences_type",
        ),
        sa.PrimaryKeyConstraint("user_id", "notification_type", name="pk_notification_preferences"),
    )
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("user_session_id", sa.UUID(), nullable=False),
        sa.Column("endpoint_hash", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh_key", sa.Text(), nullable=False),
        sa.Column("auth_key", sa.Text(), nullable=False),
        sa.Column("locale", sa.String(length=2), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
        sa.CheckConstraint("locale IN ('en', 'ja')", name="ck_push_subscriptions_locale"),
        sa.CheckConstraint("failure_count >= 0", name="ck_push_subscriptions_failure_count"),
        sa.PrimaryKeyConstraint("id", name="pk_push_subscriptions"),
        sa.UniqueConstraint("endpoint_hash", name="uq_push_subscriptions_endpoint_hash"),
    )
    op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"], unique=False)
    op.create_index("ix_push_subscriptions_user_session_id", "push_subscriptions", ["user_session_id"], unique=False)
    op.create_table(
        "notification_deliveries",
        sa.Column("outbox_id", sa.UUID(), nullable=False),
        sa.Column("subscription_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=128), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'sent', 'failed')", name="ck_notification_deliveries_status"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_notification_deliveries_attempt_count"),
        sa.CheckConstraint(
            "(status = 'pending' AND processed_at IS NULL) OR (status IN ('sent', 'failed') AND processed_at IS NOT NULL)",
            name="ck_notification_deliveries_processed_at",
        ),
        sa.PrimaryKeyConstraint("outbox_id", "subscription_id", name="pk_notification_deliveries"),
    )
    op.create_index(
        "ix_notification_deliveries_subscription_id",
        "notification_deliveries",
        ["subscription_id"],
        unique=False,
    )
    op.create_table(
        "maintenance_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(status = 'running' AND finished_at IS NULL) OR (status <> 'running' AND finished_at IS NOT NULL)",
            name="ck_maintenance_runs_finished_at",
        ),
        sa.CheckConstraint(
            "job_type IN ('photo_integrity', 'database_backup', 'secondary_storage_backup', 'trash_purge', 'restore_drill')",
            name="ck_maintenance_runs_job_type",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'warning', 'failed')", name="ck_maintenance_runs_status"
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at", name="ck_maintenance_runs_finished_after_started"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_maintenance_runs"),
    )
    op.create_index(
        "ix_maintenance_runs_job_type_started_at",
        "maintenance_runs",
        ["job_type", sa.literal_column("started_at DESC")],
        unique=False,
    )
    op.create_table(
        "administrative_audit_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("actor_username", sa.String(length=64), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_administrative_audit_events"),
    )
    op.create_index(
        "ix_administrative_audit_events_created_at_id",
        "administrative_audit_events",
        [sa.literal_column("created_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_index(
        "ix_administrative_audit_events_group_id_created_at",
        "administrative_audit_events",
        ["group_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_foreign_key(
        "fk_notification_outbox_recipient_user_id_users",
        "notification_outbox",
        "users",
        ["recipient_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_notification_preferences_user_id_users",
        "notification_preferences",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_push_subscriptions_user_id_users", "push_subscriptions", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_push_subscriptions_user_session_user_id_user_sessions",
        "push_subscriptions",
        "user_sessions",
        ["user_session_id", "user_id"],
        ["id", "user_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_notification_deliveries_outbox_id_notification_outbox",
        "notification_deliveries",
        "notification_outbox",
        ["outbox_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_notification_deliveries_subscription_id_push_subscriptions",
        "notification_deliveries",
        "push_subscriptions",
        ["subscription_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_notification_deliveries_subscription_id_push_subscriptions", "notification_deliveries", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_notification_deliveries_outbox_id_notification_outbox", "notification_deliveries", type_="foreignkey"
    )
    op.drop_index("ix_notification_deliveries_subscription_id", table_name="notification_deliveries")
    op.drop_constraint(
        "fk_push_subscriptions_user_session_user_id_user_sessions", "push_subscriptions", type_="foreignkey"
    )
    op.drop_constraint("fk_push_subscriptions_user_id_users", "push_subscriptions", type_="foreignkey")
    op.drop_constraint("fk_notification_preferences_user_id_users", "notification_preferences", type_="foreignkey")
    op.drop_constraint("fk_notification_outbox_recipient_user_id_users", "notification_outbox", type_="foreignkey")
    op.drop_table("notification_deliveries")
    op.drop_index("ix_push_subscriptions_user_session_id", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
    op.drop_table("notification_preferences")
    op.drop_index("ix_notification_outbox_pending", table_name="notification_outbox")
    op.drop_table("notification_outbox")
    op.drop_index("ix_maintenance_runs_job_type_started_at", table_name="maintenance_runs")
    op.drop_table("maintenance_runs")
    op.drop_index("ix_administrative_audit_events_group_id_created_at", table_name="administrative_audit_events")
    op.drop_index("ix_administrative_audit_events_created_at_id", table_name="administrative_audit_events")
    op.drop_table("administrative_audit_events")
