"""Replace fixed cleaning categories with group-owned categories.

Revision ID: 20260821_04_cleaning_categories
Revises: 20260821_03_household
Create Date: 2026-08-21

"""

# Alembic operations are kept explicit so this revision remains independent
# from the evolving SQLAlchemy model definitions.
# ruff: noqa: E501

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_04_cleaning_categories"
down_revision: str | None = "20260821_03_household"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "cleaning_categories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 40", name="ck_cleaning_categories_name_length"),
        sa.CheckConstraint("name = btrim(name)", name="ck_cleaning_categories_name_trimmed"),
        sa.PrimaryKeyConstraint("id", name="pk_cleaning_categories"),
    )
    op.create_index("ix_cleaning_categories_group_id", "cleaning_categories", ["group_id"], unique=False)
    op.create_index(
        "uq_cleaning_categories_group_name_ci",
        "cleaning_categories",
        ["group_id", sa.literal_column("lower(name)")],
        unique=True,
    )
    op.create_foreign_key(
        "fk_cleaning_categories_group_id_family_groups",
        "cleaning_categories",
        "family_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("ck_cleaning_tasks_category", "cleaning_tasks", type_="check")
    op.drop_column("cleaning_tasks", "category")
    op.add_column("cleaning_tasks", sa.Column("category_id", sa.UUID(), nullable=False))
    op.create_index("ix_cleaning_tasks_category_id", "cleaning_tasks", ["category_id"], unique=False)
    op.create_foreign_key(
        "fk_cleaning_tasks_category_id_cleaning_categories",
        "cleaning_tasks",
        "cleaning_categories",
        ["category_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_cleaning_tasks_category_id_cleaning_categories",
        "cleaning_tasks",
        type_="foreignkey",
    )
    op.drop_index("ix_cleaning_tasks_category_id", table_name="cleaning_tasks")
    op.drop_column("cleaning_tasks", "category_id")
    op.add_column("cleaning_tasks", sa.Column("category", sa.String(length=16), nullable=False))
    op.create_check_constraint(
        "ck_cleaning_tasks_category",
        "cleaning_tasks",
        "category IN ('watering', 'cleaning', 'children')",
    )

    op.drop_constraint(
        "fk_cleaning_categories_group_id_family_groups",
        "cleaning_categories",
        type_="foreignkey",
    )
    op.drop_index("uq_cleaning_categories_group_name_ci", table_name="cleaning_categories")
    op.drop_index("ix_cleaning_categories_group_id", table_name="cleaning_categories")
    op.drop_table("cleaning_categories")
