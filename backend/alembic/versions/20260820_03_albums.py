"""Create album schema.

Revision ID: 20260820_03
Revises: 20260820_02
Create Date: 2026-08-20

"""

# Alembic operations are kept explicit so this revision remains independent
# from the evolving SQLAlchemy model definitions.
# ruff: noqa: E501

import sqlalchemy as sa

from alembic import op

revision: str = "20260820_03"
down_revision: str | None = "20260820_02"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "album_photos",
        sa.Column("album_id", sa.UUID(), nullable=False),
        sa.Column("photo_id", sa.UUID(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("album_id", "photo_id", name="pk_album_photos"),
    )
    op.create_index("ix_album_photos_photo_id", "album_photos", ["photo_id"], unique=False)
    op.create_table(
        "albums",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_by_username", sa.String(length=64), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("cover_photo_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("char_length(title) BETWEEN 1 AND 120", name="ck_albums_title_length"),
        sa.CheckConstraint(
            "description IS NULL OR char_length(description) <= 2000", name="ck_albums_description_length"
        ),
        sa.CheckConstraint("title = btrim(title)", name="ck_albums_title_trimmed"),
        sa.PrimaryKeyConstraint("id", name="pk_albums"),
    )
    op.create_index("ix_albums_created_by_user_id", "albums", ["created_by_user_id"], unique=False)
    op.create_index("ix_albums_group_id", "albums", ["group_id"], unique=False)
    op.create_index(
        "ix_albums_updated_at_id",
        "albums",
        [sa.literal_column("updated_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_foreign_key(
        "fk_album_photos_album_id_albums", "album_photos", "albums", ["album_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_album_photos_photo_id_photos", "album_photos", "photos", ["photo_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_albums_created_by_user_id_users", "albums", "users", ["created_by_user_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        "fk_albums_group_id_family_groups", "albums", "family_groups", ["group_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_albums_cover_album_photos",
        "albums",
        "album_photos",
        ["id", "cover_photo_id"],
        ["album_id", "photo_id"],
        deferrable=True,
        initially="DEFERRED",
    )


def downgrade() -> None:
    op.drop_constraint("fk_albums_cover_album_photos", "albums", type_="foreignkey")
    op.drop_constraint("fk_albums_group_id_family_groups", "albums", type_="foreignkey")
    op.drop_constraint("fk_albums_created_by_user_id_users", "albums", type_="foreignkey")
    op.drop_constraint("fk_album_photos_photo_id_photos", "album_photos", type_="foreignkey")
    op.drop_constraint("fk_album_photos_album_id_albums", "album_photos", type_="foreignkey")
    op.drop_index("ix_albums_updated_at_id", table_name="albums")
    op.drop_index("ix_albums_group_id", table_name="albums")
    op.drop_index("ix_albums_created_by_user_id", table_name="albums")
    op.drop_table("albums")
    op.drop_index("ix_album_photos_photo_id", table_name="album_photos")
    op.drop_table("album_photos")
