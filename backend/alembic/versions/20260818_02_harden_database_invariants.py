"""Harden cross-row and lifecycle invariants.

Revision ID: 20260818_02
Revises: 20260818_01
Create Date: 2026-08-18

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_02"
down_revision: str | None = "20260818_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_users_username_trimmed",
        "users",
        "username = btrim(username)",
    )
    op.create_check_constraint(
        "ck_users_username_length",
        "users",
        "char_length(username) BETWEEN 1 AND 64",
    )
    op.create_check_constraint(
        "ck_user_invitations_username_trimmed",
        "user_invitations",
        "username = btrim(username)",
    )
    op.create_check_constraint(
        "ck_user_invitations_username_length",
        "user_invitations",
        "char_length(username) BETWEEN 1 AND 64",
    )
    op.create_unique_constraint(
        "uq_user_sessions_id_user_id",
        "user_sessions",
        ["id", "user_id"],
    )
    op.create_check_constraint(
        "ck_user_sessions_expires_after_created",
        "user_sessions",
        "expires_at > created_at",
    )
    op.drop_constraint(
        "fk_push_subscriptions_user_session_id_user_sessions",
        "push_subscriptions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_push_subscriptions_user_session_user_id_user_sessions",
        "push_subscriptions",
        "user_sessions",
        ["user_session_id", "user_id"],
        ["id", "user_id"],
        ondelete="CASCADE",
    )

    op.create_check_constraint(
        "ck_group_membership_invitations_responded_at",
        "family_group_membership_invitations",
        "(status = 'pending' AND responded_at IS NULL) OR (status <> 'pending' AND responded_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_upload_batches_completed_at",
        "upload_batches",
        "(status = 'active' AND completed_at IS NULL) OR (status <> 'active' AND completed_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_upload_items_lifecycle_fields",
        "upload_items",
        "(status IN ('queued', 'uploading', 'processing') AND completed_at IS NULL "
        "AND photo_id IS NULL AND error_code IS NULL) OR "
        "(status = 'succeeded' AND completed_at IS NOT NULL AND error_code IS NULL) OR "
        "(status = 'duplicate' AND completed_at IS NOT NULL AND photo_id IS NULL "
        "AND error_code = 'duplicate') OR "
        "(status = 'failed' AND completed_at IS NOT NULL AND photo_id IS NULL "
        "AND error_code IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_notification_outbox_lifecycle_fields",
        "notification_outbox",
        "(status = 'pending' AND processed_at IS NULL AND claimed_at IS NULL AND claim_token IS NULL) OR "
        "(status = 'processing' AND processed_at IS NULL AND claimed_at IS NOT NULL AND claim_token IS NOT NULL) OR "
        "(status IN ('sent', 'failed') AND processed_at IS NOT NULL AND claimed_at IS NULL AND claim_token IS NULL)",
    )
    op.create_check_constraint(
        "ck_notification_deliveries_processed_at",
        "notification_deliveries",
        "(status = 'pending' AND processed_at IS NULL) OR (status IN ('sent', 'failed') AND processed_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_maintenance_runs_finished_after_started",
        "maintenance_runs",
        "finished_at IS NULL OR finished_at >= started_at",
    )

    op.create_index("ix_photos_trashed_by_user_id", "photos", ["trashed_by_user_id"])
    op.create_index(
        "ix_group_membership_invitations_group_id",
        "family_group_membership_invitations",
        ["group_id"],
    )
    op.create_index(
        "ix_group_membership_invitations_requested_by_user_id",
        "family_group_membership_invitations",
        ["requested_by_user_id"],
    )
    op.create_index(
        "ix_cleaning_completions_completed_by_user_id",
        "cleaning_completions",
        ["completed_by_user_id"],
    )
    op.create_index("ix_shopping_items_created_by_user_id", "shopping_items", ["created_by_user_id"])
    op.create_index("ix_shopping_items_purchased_by_user_id", "shopping_items", ["purchased_by_user_id"])
    op.create_index("ix_upload_batch_group_shares_group_id", "upload_batch_group_shares", ["group_id"])
    op.create_index("ix_upload_items_photo_id", "upload_items", ["photo_id"])
    op.create_index("ix_notification_deliveries_subscription_id", "notification_deliveries", ["subscription_id"])
    op.drop_index("ix_notification_outbox_pending", table_name="notification_outbox")
    op.create_index(
        "ix_notification_outbox_pending",
        "notification_outbox",
        ["available_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("ix_notification_outbox_pending", table_name="notification_outbox")
    op.create_index(
        "ix_notification_outbox_pending",
        "notification_outbox",
        ["status", "available_at"],
    )
    op.drop_index("ix_notification_deliveries_subscription_id", table_name="notification_deliveries")
    op.drop_index("ix_upload_items_photo_id", table_name="upload_items")
    op.drop_index("ix_upload_batch_group_shares_group_id", table_name="upload_batch_group_shares")
    op.drop_index("ix_shopping_items_purchased_by_user_id", table_name="shopping_items")
    op.drop_index("ix_shopping_items_created_by_user_id", table_name="shopping_items")
    op.drop_index("ix_cleaning_completions_completed_by_user_id", table_name="cleaning_completions")
    op.drop_index(
        "ix_group_membership_invitations_requested_by_user_id",
        table_name="family_group_membership_invitations",
    )
    op.drop_index("ix_group_membership_invitations_group_id", table_name="family_group_membership_invitations")
    op.drop_index("ix_photos_trashed_by_user_id", table_name="photos")

    op.drop_constraint(
        "ck_maintenance_runs_finished_after_started",
        "maintenance_runs",
        type_="check",
    )
    op.drop_constraint(
        "ck_notification_deliveries_processed_at",
        "notification_deliveries",
        type_="check",
    )
    op.drop_constraint(
        "ck_notification_outbox_lifecycle_fields",
        "notification_outbox",
        type_="check",
    )
    op.drop_constraint("ck_upload_items_lifecycle_fields", "upload_items", type_="check")
    op.drop_constraint("ck_upload_batches_completed_at", "upload_batches", type_="check")
    op.drop_constraint(
        "ck_group_membership_invitations_responded_at",
        "family_group_membership_invitations",
        type_="check",
    )

    op.drop_constraint(
        "fk_push_subscriptions_user_session_user_id_user_sessions",
        "push_subscriptions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_push_subscriptions_user_session_id_user_sessions",
        "push_subscriptions",
        "user_sessions",
        ["user_session_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("ck_user_sessions_expires_after_created", "user_sessions", type_="check")
    op.drop_constraint("uq_user_sessions_id_user_id", "user_sessions", type_="unique")
    op.drop_constraint("ck_user_invitations_username_length", "user_invitations", type_="check")
    op.drop_constraint("ck_user_invitations_username_trimmed", "user_invitations", type_="check")
    op.drop_constraint("ck_users_username_length", "users", type_="check")
    op.drop_constraint("ck_users_username_trimmed", "users", type_="check")
