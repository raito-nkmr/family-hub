"""Create the core identity and family-group schema.

Revision ID: 20260821_01_core
Revises:
Create Date: 2026-08-21

"""

# Alembic operations are kept explicit so this revision remains independent
# from the evolving SQLAlchemy model definitions.
# ruff: noqa: E501

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_01_core"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("system_role", sa.String(length=16), server_default="user", nullable=False),
        sa.Column("must_change_password", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "password_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("system_role IN ('admin', 'user')", name="ck_users_system_role"),
        sa.CheckConstraint("username = btrim(username)", name="ck_users_username_trimmed"),
        sa.CheckConstraint("char_length(username) BETWEEN 1 AND 64", name="ck_users_username_length"),
        sa.CheckConstraint("username = lower(username)", name="ck_users_username_lowercase"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token", sa.String(length=43), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("csrf_token ~ '^[A-Za-z0-9_-]{43}$'", name="ck_user_sessions_csrf_token"),
        sa.CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="ck_user_sessions_token_hash_lower_hex"),
        sa.CheckConstraint("expires_at > created_at", name="ck_user_sessions_expires_after_created"),
        sa.PrimaryKeyConstraint("id", name="pk_user_sessions"),
        sa.UniqueConstraint("id", "user_id", name="uq_user_sessions_id_user_id"),
        sa.UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"], unique=False)
    op.create_table(
        "user_invitations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="ck_user_invitations_token_hash_lower_hex"),
        sa.CheckConstraint("username = lower(username)", name="ck_user_invitations_username_lowercase"),
        sa.CheckConstraint("username = btrim(username)", name="ck_user_invitations_username_trimmed"),
        sa.CheckConstraint("char_length(username) BETWEEN 1 AND 64", name="ck_user_invitations_username_length"),
        sa.PrimaryKeyConstraint("id", name="pk_user_invitations"),
        sa.UniqueConstraint("token_hash", name="uq_user_invitations_token_hash"),
    )
    op.create_index(
        "ix_user_invitations_created_at",
        "user_invitations",
        [sa.literal_column("created_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_index(
        "uq_user_invitations_pending_username",
        "user_invitations",
        ["username"],
        unique=True,
        postgresql_where=sa.text("used_at IS NULL AND revoked_at IS NULL"),
    )
    op.create_table(
        "family_groups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 120", name="ck_family_groups_name_length"),
        sa.CheckConstraint("name = btrim(name)", name="ck_family_groups_name_trimmed"),
        sa.PrimaryKeyConstraint("id", name="pk_family_groups"),
        sa.UniqueConstraint("name", name="uq_family_groups_name"),
    )
    op.create_index("ix_family_groups_created_by_user_id", "family_groups", ["created_by_user_id"], unique=False)
    op.create_table(
        "family_group_members",
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'member')", name="ck_family_group_members_role"),
        sa.PrimaryKeyConstraint("group_id", "user_id", name="pk_family_group_members"),
    )
    op.create_index("ix_family_group_members_user_id", "family_group_members", ["user_id"], unique=False)
    op.create_table(
        "family_group_membership_invitations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("requested_by_user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('admin', 'member')", name="ck_group_membership_invitations_role"),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'canceled')", name="ck_group_membership_invitations_status"
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND responded_at IS NULL) OR (status <> 'pending' AND responded_at IS NOT NULL)",
            name="ck_group_membership_invitations_responded_at",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_group_membership_invitations"),
    )
    op.create_index(
        "ix_group_membership_invitations_user_status",
        "family_group_membership_invitations",
        ["user_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_group_membership_invitations_pending",
        "family_group_membership_invitations",
        ["group_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_group_membership_invitations_group_id",
        "family_group_membership_invitations",
        ["group_id"],
        unique=False,
    )
    op.create_index(
        "ix_group_membership_invitations_requested_by_user_id",
        "family_group_membership_invitations",
        ["requested_by_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_family_groups_created_by_user_id_users",
        "family_groups",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_user_invitations_created_by_user_id_users",
        "user_invitations",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_user_sessions_user_id_users", "user_sessions", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_family_group_members_group_id_family_groups",
        "family_group_members",
        "family_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_family_group_members_user_id_users",
        "family_group_members",
        "users",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_group_membership_invitations_group_id",
        "family_group_membership_invitations",
        "family_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_group_membership_invitations_requested_by_user_id",
        "family_group_membership_invitations",
        "users",
        ["requested_by_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_group_membership_invitations_user_id",
        "family_group_membership_invitations",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_group_membership_invitations_user_id", "family_group_membership_invitations", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_group_membership_invitations_requested_by_user_id",
        "family_group_membership_invitations",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_group_membership_invitations_group_id", "family_group_membership_invitations", type_="foreignkey"
    )
    op.drop_constraint("fk_family_group_members_user_id_users", "family_group_members", type_="foreignkey")
    op.drop_constraint("fk_family_group_members_group_id_family_groups", "family_group_members", type_="foreignkey")
    op.drop_constraint("fk_user_sessions_user_id_users", "user_sessions", type_="foreignkey")
    op.drop_constraint("fk_user_invitations_created_by_user_id_users", "user_invitations", type_="foreignkey")
    op.drop_constraint("fk_family_groups_created_by_user_id_users", "family_groups", type_="foreignkey")
    op.drop_index(
        "uq_group_membership_invitations_pending",
        table_name="family_group_membership_invitations",
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.drop_index(
        "ix_group_membership_invitations_requested_by_user_id", table_name="family_group_membership_invitations"
    )
    op.drop_index("ix_group_membership_invitations_group_id", table_name="family_group_membership_invitations")
    op.drop_index("ix_group_membership_invitations_user_status", table_name="family_group_membership_invitations")
    op.drop_table("family_group_membership_invitations")
    op.drop_index("ix_family_group_members_user_id", table_name="family_group_members")
    op.drop_table("family_group_members")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index(
        "uq_user_invitations_pending_username",
        table_name="user_invitations",
        postgresql_where=sa.text("used_at IS NULL AND revoked_at IS NULL"),
    )
    op.drop_index("ix_user_invitations_created_at", table_name="user_invitations")
    op.drop_table("user_invitations")
    op.drop_index("ix_family_groups_created_by_user_id", table_name="family_groups")
    op.drop_table("family_groups")
    op.drop_table("users")
