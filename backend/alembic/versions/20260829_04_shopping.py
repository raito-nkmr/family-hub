"""Create the complete shopping schema, including discarded trip state.

Revision ID: 20260829_04_shopping
Revises: 20260829_03_household
Create Date: 2026-08-29

This revision is schema-only. Existing application data is not transformed.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "20260829_04_shopping"
down_revision: str | None = "20260829_03_household"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "shopping_categories",
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
        sa.CheckConstraint("name = btrim(name)", name="ck_shopping_categories_name_trimmed"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 40", name="ck_shopping_categories_name_length"),
        sa.CheckConstraint("sort_order >= 0", name="ck_shopping_categories_sort_order"),
        sa.PrimaryKeyConstraint("id", name="pk_shopping_categories"),
    )
    op.create_foreign_key(
        "fk_shopping_categories_group_id_family_groups",
        "shopping_categories",
        "family_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_shopping_categories_group_id", "shopping_categories", ["group_id"], unique=False)
    op.create_index(
        "uq_shopping_categories_group_name_ci",
        "shopping_categories",
        ["group_id", sa.literal_column("lower(name)")],
        unique=True,
    )
    op.create_index(
        "ix_shopping_categories_group_sort_order",
        "shopping_categories",
        ["group_id", "sort_order", "id"],
        unique=False,
    )

    op.add_column(
        "shopping_items",
        sa.Column("assignee_user_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "shopping_items",
        sa.Column("category_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_shopping_items_assignee_user_id_users",
        "shopping_items",
        "users",
        ["assignee_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_shopping_items_category_id_shopping_categories",
        "shopping_items",
        "shopping_categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_shopping_items_assignee_user_id", "shopping_items", ["assignee_user_id"], unique=False)
    op.create_index("ix_shopping_items_category_id", "shopping_items", ["category_id"], unique=False)

    op.create_table(
        "shopping_trips",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("started_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_amount_yen", sa.Integer(), nullable=True),
        sa.Column("recorded_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint(
            "total_amount_yen IS NULL OR total_amount_yen >= 0",
            name="ck_shopping_trips_amount_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_shopping_trips"),
    )
    op.create_foreign_key(
        "fk_shopping_trips_group_id_family_groups",
        "shopping_trips",
        "family_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_shopping_trips_started_by_user_id_users",
        "shopping_trips",
        "users",
        ["started_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_shopping_trips_recorded_by_user_id_users",
        "shopping_trips",
        "users",
        ["recorded_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_shopping_trips_group_started_at",
        "shopping_trips",
        ["group_id", sa.literal_column("started_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_index("ix_shopping_trips_started_by_user_id", "shopping_trips", ["started_by_user_id"], unique=False)

    op.create_table(
        "shopping_purchases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("shopping_item_id", sa.UUID(), nullable=True),
        sa.Column("item_name_snapshot", sa.String(length=120), nullable=False),
        sa.Column("assignee_user_id", sa.UUID(), nullable=True),
        sa.Column("assignee_username_snapshot", sa.String(length=120), nullable=True),
        sa.Column("category_id", sa.UUID(), nullable=True),
        sa.Column("category_name_snapshot", sa.String(length=40), nullable=True),
        sa.Column("purchased_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "purchased_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.CheckConstraint(
            "(reversed_at IS NULL AND reversed_by_user_id IS NULL) OR "
            "(reversed_at IS NOT NULL AND reversed_by_user_id IS NOT NULL)",
            name="ck_shopping_purchases_reversal_state",
        ),
        sa.CheckConstraint("item_name_snapshot = btrim(item_name_snapshot)", name="ck_shopping_purchases_name_trimmed"),
        sa.CheckConstraint(
            "char_length(item_name_snapshot) BETWEEN 1 AND 120", name="ck_shopping_purchases_name_length"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_shopping_purchases"),
    )
    op.create_foreign_key(
        "fk_shopping_purchases_group_id_family_groups",
        "shopping_purchases",
        "family_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_shopping_purchases_trip_id_shopping_trips",
        "shopping_purchases",
        "shopping_trips",
        ["trip_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_shopping_purchases_item_id_shopping_items",
        "shopping_purchases",
        "shopping_items",
        ["shopping_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_shopping_purchases_assignee_user_id_users",
        "shopping_purchases",
        "users",
        ["assignee_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_shopping_purchases_category_id_shopping_categories",
        "shopping_purchases",
        "shopping_categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_shopping_purchases_purchased_by_user_id_users",
        "shopping_purchases",
        "users",
        ["purchased_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_shopping_purchases_reversed_by_user_id_users",
        "shopping_purchases",
        "users",
        ["reversed_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_shopping_purchases_group_purchased_at",
        "shopping_purchases",
        ["group_id", sa.literal_column("purchased_at DESC")],
        unique=False,
    )
    op.create_index("ix_shopping_purchases_trip_id", "shopping_purchases", ["trip_id"], unique=False)
    op.create_index("ix_shopping_purchases_item_id", "shopping_purchases", ["shopping_item_id"], unique=False)
    op.create_index(
        "ix_shopping_purchases_purchased_by_user_id",
        "shopping_purchases",
        ["purchased_by_user_id"],
        unique=False,
    )
    # Discarded shopping-trip state.
    op.add_column("shopping_trips", sa.Column("discarded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shopping_trips", sa.Column("discarded_by_user_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_shopping_trips_discarded_by_user_id_users",
        "shopping_trips",
        "users",
        ["discarded_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_shopping_trips_discard_state",
        "shopping_trips",
        "(discarded_at IS NULL AND discarded_by_user_id IS NULL) OR "
        "(discarded_at IS NOT NULL AND discarded_by_user_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_shopping_trips_discard_not_finalized",
        "shopping_trips",
        "discarded_at IS NULL OR finalized_at IS NULL",
    )
    op.create_index(
        "ix_shopping_trips_discarded_by_user_id",
        "shopping_trips",
        ["discarded_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    # Discarded shopping-trip state.
    op.drop_index("ix_shopping_trips_discarded_by_user_id", table_name="shopping_trips")
    op.drop_constraint("ck_shopping_trips_discard_not_finalized", "shopping_trips", type_="check")
    op.drop_constraint("ck_shopping_trips_discard_state", "shopping_trips", type_="check")
    op.drop_constraint("fk_shopping_trips_discarded_by_user_id_users", "shopping_trips", type_="foreignkey")
    op.drop_column("shopping_trips", "discarded_by_user_id")
    op.drop_column("shopping_trips", "discarded_at")

    op.drop_index("ix_shopping_purchases_purchased_by_user_id", table_name="shopping_purchases")
    op.drop_index("ix_shopping_purchases_item_id", table_name="shopping_purchases")
    op.drop_index("ix_shopping_purchases_trip_id", table_name="shopping_purchases")
    op.drop_index("ix_shopping_purchases_group_purchased_at", table_name="shopping_purchases")
    for name in (
        "fk_shopping_purchases_reversed_by_user_id_users",
        "fk_shopping_purchases_purchased_by_user_id_users",
        "fk_shopping_purchases_category_id_shopping_categories",
        "fk_shopping_purchases_assignee_user_id_users",
        "fk_shopping_purchases_item_id_shopping_items",
        "fk_shopping_purchases_trip_id_shopping_trips",
        "fk_shopping_purchases_group_id_family_groups",
    ):
        op.drop_constraint(name, "shopping_purchases", type_="foreignkey")
    op.drop_table("shopping_purchases")

    op.drop_index("ix_shopping_trips_started_by_user_id", table_name="shopping_trips")
    op.drop_index("ix_shopping_trips_group_started_at", table_name="shopping_trips")
    for name in (
        "fk_shopping_trips_recorded_by_user_id_users",
        "fk_shopping_trips_started_by_user_id_users",
        "fk_shopping_trips_group_id_family_groups",
    ):
        op.drop_constraint(name, "shopping_trips", type_="foreignkey")
    op.drop_table("shopping_trips")

    op.drop_index("ix_shopping_items_category_id", table_name="shopping_items")
    op.drop_index("ix_shopping_items_assignee_user_id", table_name="shopping_items")
    op.drop_constraint("fk_shopping_items_category_id_shopping_categories", "shopping_items", type_="foreignkey")
    op.drop_constraint("fk_shopping_items_assignee_user_id_users", "shopping_items", type_="foreignkey")
    op.drop_column("shopping_items", "category_id")
    op.drop_column("shopping_items", "assignee_user_id")

    op.drop_index("ix_shopping_categories_group_sort_order", table_name="shopping_categories")
    op.drop_index("uq_shopping_categories_group_name_ci", table_name="shopping_categories")
    op.drop_index("ix_shopping_categories_group_id", table_name="shopping_categories")
    op.drop_constraint("fk_shopping_categories_group_id_family_groups", "shopping_categories", type_="foreignkey")
    op.drop_table("shopping_categories")
