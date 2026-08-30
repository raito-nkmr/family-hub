"""Remove the legacy single album group column.

Revision ID: 20260830_02_drop_album_group
Revises: 20260830_01_album_groups
Create Date: 2026-08-30

Run the migrate_album_group_shares management command after the previous
revision and before applying this revision in an environment with existing
albums.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_02_drop_album_group"
down_revision: str | None = "20260830_01_album_groups"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("LOCK TABLE albums, album_group_shares IN SHARE ROW EXCLUSIVE MODE")
    op.execute(
        """
        DO $migration$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM albums AS album
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM album_group_shares AS share
                    WHERE share.album_id = album.id
                )
                OR (
                    album.group_id IS NOT NULL
                    AND NOT EXISTS (
                        SELECT 1
                        FROM album_group_shares AS legacy_share
                        WHERE legacy_share.album_id = album.id
                        AND legacy_share.group_id = album.group_id
                    )
                )
            ) THEN
                RAISE EXCEPTION
                    'Cannot remove albums.group_id before every album group share has been migrated';
            END IF;
        END
        $migration$
        """
    )
    op.drop_constraint("fk_albums_group_id_family_groups", "albums", type_="foreignkey")
    op.drop_index("ix_albums_group_id", table_name="albums")
    op.drop_column("albums", "group_id")


def downgrade() -> None:
    op.add_column("albums", sa.Column("group_id", sa.UUID(), nullable=True))
    op.create_index("ix_albums_group_id", "albums", ["group_id"], unique=False)
    op.create_foreign_key(
        "fk_albums_group_id_family_groups",
        "albums",
        "family_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
