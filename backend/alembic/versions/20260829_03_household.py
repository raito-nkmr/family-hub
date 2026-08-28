"""Create household, notification, maintenance, and audit schema.

Revision ID: 20260829_03_household
Revises: 20260829_02_media
Create Date: 2026-08-29

"""

# Alembic operations are kept explicit so this revision remains independent
# from the evolving SQLAlchemy model definitions.
# ruff: noqa: E501

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260829_03_household"
down_revision: str | None = "20260829_02_media"
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
    op.create_table(
        "chore_categories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("name = btrim(name)", name="ck_chore_categories_name_trimmed"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 40", name="ck_chore_categories_name_length"),
        sa.CheckConstraint("sort_order >= 0", name="ck_chore_categories_sort_order"),
        sa.PrimaryKeyConstraint("id", name="pk_chore_categories"),
    )
    op.create_index("ix_chore_categories_group_id", "chore_categories", ["group_id"], unique=False)
    op.create_index(
        "uq_chore_categories_group_name_ci",
        "chore_categories",
        ["group_id", sa.literal_column("lower(name)")],
        unique=True,
    )
    op.create_index(
        "ix_chore_categories_group_sort_order",
        "chore_categories",
        ["group_id", "sort_order", "id"],
        unique=False,
    )
    op.create_table(
        "chore_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("task_name", sa.String(length=120), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("char_length(task_name) BETWEEN 1 AND 120", name="ck_chore_tasks_task_name_length"),
        sa.CheckConstraint("interval_days BETWEEN 1 AND 3650", name="ck_chore_tasks_interval_days"),
        sa.CheckConstraint("task_name = btrim(task_name)", name="ck_chore_tasks_task_name_trimmed"),
        sa.PrimaryKeyConstraint("id", name="pk_chore_tasks"),
    )
    op.create_index("ix_chore_tasks_group_id_is_active", "chore_tasks", ["group_id", "is_active"], unique=False)
    op.create_index("ix_chore_tasks_category_id", "chore_tasks", ["category_id"], unique=False)
    op.create_table(
        "chore_completions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("task_name_snapshot", sa.String(length=120), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=True),
        sa.Column("category_name_snapshot", sa.String(length=40), nullable=False),
        sa.Column("completed_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint(
            "task_name_snapshot = btrim(task_name_snapshot)",
            name="ck_chore_completions_task_name_trimmed",
        ),
        sa.CheckConstraint(
            "char_length(task_name_snapshot) BETWEEN 1 AND 120",
            name="ck_chore_completions_task_name_length",
        ),
        sa.CheckConstraint(
            "category_name_snapshot = btrim(category_name_snapshot)",
            name="ck_chore_completions_category_name_trimmed",
        ),
        sa.CheckConstraint(
            "char_length(category_name_snapshot) BETWEEN 1 AND 40",
            name="ck_chore_completions_category_name_length",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chore_completions"),
    )
    op.create_index(
        "ix_chore_completions_task_id_completed_at",
        "chore_completions",
        ["task_id", sa.literal_column("completed_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_index(
        "ix_chore_completions_completed_by_user_id",
        "chore_completions",
        ["completed_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_chore_completions_completed_at_task_id",
        "chore_completions",
        ["completed_at", "task_id"],
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
        "fk_chore_tasks_created_by_user_id_users",
        "chore_tasks",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_chore_tasks_group_id_family_groups",
        "chore_tasks",
        "family_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_chore_categories_group_id_family_groups",
        "chore_categories",
        "family_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_chore_tasks_category_id_chore_categories",
        "chore_tasks",
        "chore_categories",
        ["category_id"],
        ["id"],
        ondelete="RESTRICT",
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
        "fk_chore_completions_completed_by_user_id_users",
        "chore_completions",
        "users",
        ["completed_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_chore_completions_task_id_chore_tasks",
        "chore_completions",
        "chore_tasks",
        ["task_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_chore_completions_category_id_chore_categories",
        "chore_completions",
        "chore_categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )
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
            "notification_type IN ('photo_shared', 'chore_due', 'shopping_added')",
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
            "notification_type IN ('photo_shared', 'chore_due', 'shopping_added')",
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
    op.drop_constraint("fk_chore_completions_category_id_chore_categories", "chore_completions", type_="foreignkey")
    op.drop_constraint("fk_chore_completions_task_id_chore_tasks", "chore_completions", type_="foreignkey")
    op.drop_constraint("fk_chore_completions_completed_by_user_id_users", "chore_completions", type_="foreignkey")
    op.drop_constraint("fk_shopping_items_purchased_by_user_id_users", "shopping_items", type_="foreignkey")
    op.drop_constraint("fk_shopping_items_group_id_family_groups", "shopping_items", type_="foreignkey")
    op.drop_constraint("fk_shopping_items_created_by_user_id_users", "shopping_items", type_="foreignkey")
    op.drop_constraint("fk_chore_tasks_group_id_family_groups", "chore_tasks", type_="foreignkey")
    op.drop_constraint("fk_chore_tasks_created_by_user_id_users", "chore_tasks", type_="foreignkey")
    op.drop_index("ix_chore_completions_task_id_completed_at", table_name="chore_completions")
    op.drop_index("ix_chore_completions_completed_by_user_id", table_name="chore_completions")
    op.drop_index("ix_chore_completions_completed_at_task_id", table_name="chore_completions")
    op.drop_table("chore_completions")
    op.drop_index("ix_shopping_items_purchased_by_user_id", table_name="shopping_items")
    op.drop_index("ix_shopping_items_created_by_user_id", table_name="shopping_items")
    op.drop_index("ix_shopping_items_group_id_purchase_state", table_name="shopping_items")
    op.drop_table("shopping_items")
    op.drop_constraint("fk_chore_tasks_category_id_chore_categories", "chore_tasks", type_="foreignkey")
    op.drop_index("ix_chore_tasks_group_id_is_active", table_name="chore_tasks")
    op.drop_index("ix_chore_tasks_category_id", table_name="chore_tasks")
    op.drop_table("chore_tasks")
    op.drop_constraint("fk_chore_categories_group_id_family_groups", "chore_categories", type_="foreignkey")
    op.drop_index("ix_chore_categories_group_sort_order", table_name="chore_categories")
    op.drop_index("uq_chore_categories_group_name_ci", table_name="chore_categories")
    op.drop_index("ix_chore_categories_group_id", table_name="chore_categories")
    op.drop_table("chore_categories")
    op.drop_constraint("ck_family_groups_timezone_length", "family_groups", type_="check")
    op.drop_constraint("ck_family_groups_timezone_trimmed", "family_groups", type_="check")
    op.drop_column("family_groups", "timezone")
