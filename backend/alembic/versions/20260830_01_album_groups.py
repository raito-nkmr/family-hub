"""Add album group sharing associations.

Revision ID: 20260830_01_album_groups
Revises: 20260829_04_shopping
Create Date: 2026-08-30

This revision is schema-only. Existing album group associations are copied by
the separate migrate_album_group_shares management command before the legacy
column is removed by the following revision.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_01_album_groups"
down_revision: str | None = "20260829_04_shopping"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.alter_column("albums", "group_id", existing_type=sa.UUID(), nullable=True)
    op.create_table(
        "album_group_shares",
        sa.Column("album_id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.PrimaryKeyConstraint("album_id", "group_id", name="pk_album_group_shares"),
    )
    op.create_index(
        "ix_album_group_shares_group_id_album_id",
        "album_group_shares",
        ["group_id", "album_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_album_group_shares_album_id_albums",
        "album_group_shares",
        "albums",
        ["album_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_album_group_shares_group_id_family_groups",
        "album_group_shares",
        "family_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_album_group_shares_group_id_family_groups", "album_group_shares", type_="foreignkey")
    op.drop_constraint("fk_album_group_shares_album_id_albums", "album_group_shares", type_="foreignkey")
    op.drop_index("ix_album_group_shares_group_id_album_id", table_name="album_group_shares")
    op.drop_table("album_group_shares")
    op.alter_column("albums", "group_id", existing_type=sa.UUID(), nullable=False)
