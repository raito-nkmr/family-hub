"""Allow HDD-backed photo preview derivatives.

Revision ID: 20260912_01_photo_previews
Revises: 20260830_02_drop_album_group
Create Date: 2026-09-12

"""

from alembic import op

revision: str = "20260912_01_photo_previews"
down_revision: str | None = "20260830_02_drop_album_group"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.drop_constraint("ck_photo_derivatives_kind", "photo_derivatives", type_="check")
    op.create_check_constraint(
        "ck_photo_derivatives_kind",
        "photo_derivatives",
        "kind IN ('thumbnail', 'preview')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_photo_derivatives_kind", "photo_derivatives", type_="check")
    op.create_check_constraint(
        "ck_photo_derivatives_kind",
        "photo_derivatives",
        "kind IN ('thumbnail')",
    )
