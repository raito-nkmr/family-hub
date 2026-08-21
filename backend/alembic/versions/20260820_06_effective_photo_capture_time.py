"""Store the effective photo capture time for sorting.

Revision ID: 20260820_06
Revises: 20260820_05
Create Date: 2026-08-20

"""

import sqlalchemy as sa

from alembic import op

revision: str = "20260820_06"
down_revision: str | None = "20260820_05"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "photos",
        sa.Column("effective_captured_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE photos AS photos
            SET effective_captured_at = COALESCE(
                photo_metadata.captured_at_override,
                photos.captured_at,
                photos.uploaded_at
            )
            FROM photo_metadata
            WHERE photo_metadata.photo_id = photos.id
            """
        )
    )
    op.execute(sa.text("UPDATE photos SET effective_captured_at = uploaded_at WHERE effective_captured_at IS NULL"))
    op.alter_column("photos", "effective_captured_at", nullable=False)
    op.drop_index("ix_photos_sort_date_id", table_name="photos")
    op.create_index(
        "ix_photos_sort_date_id",
        "photos",
        [sa.literal_column("effective_captured_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_photos_sort_date_id", table_name="photos")
    op.create_index(
        "ix_photos_sort_date_id",
        "photos",
        [sa.literal_column("coalesce(captured_at, uploaded_at) DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.drop_column("photos", "effective_captured_at")
