"""Clarify group membership invitation columns and object names.

Revision ID: 20260822_02_invitation_names
Revises: 20260822_01_chore_task_name
Create Date: 2026-08-22

"""

from alembic import op

revision: str = "20260822_02_invitation_names"
down_revision: str | None = "20260822_01_chore_task_name"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.alter_column(
        "family_group_membership_invitations",
        "user_id",
        new_column_name="invitee_user_id",
    )
    op.alter_column(
        "family_group_membership_invitations",
        "requested_by_user_id",
        new_column_name="invited_by_user_id",
    )
    statements = (
        "ALTER TABLE family_group_membership_invitations RENAME CONSTRAINT pk_group_membership_invitations "
        "TO pk_family_group_membership_invitations",
        "ALTER TABLE family_group_membership_invitations RENAME CONSTRAINT ck_group_membership_invitations_role "
        "TO ck_family_group_membership_invitations_role",
        "ALTER TABLE family_group_membership_invitations RENAME CONSTRAINT ck_group_membership_invitations_status "
        "TO ck_family_group_membership_invitations_status",
        "ALTER TABLE family_group_membership_invitations RENAME CONSTRAINT "
        "ck_group_membership_invitations_responded_at "
        "TO ck_family_group_membership_invitations_responded_at",
        "ALTER INDEX uq_group_membership_invitations_pending RENAME TO uq_family_group_membership_invitations_pending",
        "ALTER INDEX ix_group_membership_invitations_group_id RENAME TO "
        "ix_family_group_membership_invitations_group_id",
        "ALTER INDEX ix_group_membership_invitations_user_status RENAME TO "
        "ix_family_group_membership_invitations_invitee_status",
        "ALTER INDEX ix_group_membership_invitations_requested_by_user_id RENAME TO "
        "ix_family_group_membership_invitations_invited_by_user_id",
        "ALTER TABLE family_group_membership_invitations RENAME CONSTRAINT "
        "fk_group_membership_invitations_group_id "
        "TO fk_family_group_membership_invitations_group_id_family_groups",
        "ALTER TABLE family_group_membership_invitations RENAME CONSTRAINT "
        "fk_group_membership_invitations_user_id "
        "TO fk_family_group_membership_invitations_invitee_user_id_users",
        "ALTER TABLE family_group_membership_invitations RENAME CONSTRAINT "
        "fk_group_membership_invitations_requested_by_user_id "
        "TO fk_family_group_membership_invitations_invited_by_user_id_users",
    )
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    statements = (
        "ALTER TABLE family_group_membership_invitations RENAME CONSTRAINT "
        "fk_family_group_membership_invitations_invited_by_user_id_users "
        "TO fk_group_membership_invitations_requested_by_user_id",
        "ALTER TABLE family_group_membership_invitations RENAME CONSTRAINT "
        "fk_family_group_membership_invitations_invitee_user_id_users "
        "TO fk_group_membership_invitations_user_id",
        "ALTER TABLE family_group_membership_invitations RENAME CONSTRAINT "
        "fk_family_group_membership_invitations_group_id_family_groups "
        "TO fk_group_membership_invitations_group_id",
        "ALTER INDEX ix_family_group_membership_invitations_invited_by_user_id RENAME TO "
        "ix_group_membership_invitations_requested_by_user_id",
        "ALTER INDEX ix_family_group_membership_invitations_invitee_status RENAME TO "
        "ix_group_membership_invitations_user_status",
        "ALTER INDEX ix_family_group_membership_invitations_group_id RENAME TO "
        "ix_group_membership_invitations_group_id",
        "ALTER INDEX uq_family_group_membership_invitations_pending RENAME TO uq_group_membership_invitations_pending",
        "ALTER TABLE family_group_membership_invitations RENAME CONSTRAINT "
        "ck_family_group_membership_invitations_responded_at "
        "TO ck_group_membership_invitations_responded_at",
        "ALTER TABLE family_group_membership_invitations RENAME CONSTRAINT "
        "ck_family_group_membership_invitations_status "
        "TO ck_group_membership_invitations_status",
        "ALTER TABLE family_group_membership_invitations RENAME CONSTRAINT ck_family_group_membership_invitations_role "
        "TO ck_group_membership_invitations_role",
        "ALTER TABLE family_group_membership_invitations RENAME CONSTRAINT pk_family_group_membership_invitations "
        "TO pk_group_membership_invitations",
    )
    for statement in statements:
        op.execute(statement)
    op.alter_column(
        "family_group_membership_invitations",
        "invited_by_user_id",
        new_column_name="requested_by_user_id",
    )
    op.alter_column(
        "family_group_membership_invitations",
        "invitee_user_id",
        new_column_name="user_id",
    )
