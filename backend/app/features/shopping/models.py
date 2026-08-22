from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, PrimaryKeyConstraint, String, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ShoppingItem(Base):
    __tablename__ = "shopping_items"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_shopping_items"),
        CheckConstraint("name = btrim(name)", name="ck_shopping_items_name_trimmed"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 120", name="ck_shopping_items_name_length"),
        CheckConstraint(
            "(purchased_by_user_id IS NULL AND purchased_at IS NULL) OR "
            "(purchased_by_user_id IS NOT NULL AND purchased_at IS NOT NULL)",
            name="ck_shopping_items_purchase_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    group_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("family_groups.id", ondelete="CASCADE", name="fk_shopping_items_group_id_family_groups"),
    )
    name: Mapped[str] = mapped_column(String(120))
    created_by_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_shopping_items_created_by_user_id_users"),
    )
    purchased_by_user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_shopping_items_purchased_by_user_id_users"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    purchased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assignee_user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_shopping_items_assignee_user_id_users"),
        nullable=True,
    )
    category_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "shopping_categories.id", ondelete="SET NULL", name="fk_shopping_items_category_id_shopping_categories"
        ),
        nullable=True,
    )


class ShoppingCategory(Base):
    __tablename__ = "shopping_categories"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_shopping_categories"),
        CheckConstraint("name = btrim(name)", name="ck_shopping_categories_name_trimmed"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 40", name="ck_shopping_categories_name_length"),
        CheckConstraint("sort_order >= 0", name="ck_shopping_categories_sort_order"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    group_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("family_groups.id", ondelete="CASCADE", name="fk_shopping_categories_group_id_family_groups"),
    )
    name: Mapped[str] = mapped_column(String(40))
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class ShoppingTrip(Base):
    __tablename__ = "shopping_trips"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_shopping_trips"),
        CheckConstraint(
            "total_amount_yen IS NULL OR total_amount_yen >= 0", name="ck_shopping_trips_amount_nonnegative"
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    group_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("family_groups.id", ondelete="CASCADE", name="fk_shopping_trips_group_id_family_groups"),
    )
    started_by_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_shopping_trips_started_by_user_id_users"),
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_amount_yen: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_by_user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_shopping_trips_recorded_by_user_id_users"),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class ShoppingPurchase(Base):
    __tablename__ = "shopping_purchases"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_shopping_purchases"),
        CheckConstraint(
            "(reversed_at IS NULL AND reversed_by_user_id IS NULL) OR "
            "(reversed_at IS NOT NULL AND reversed_by_user_id IS NOT NULL)",
            name="ck_shopping_purchases_reversal_state",
        ),
        CheckConstraint("item_name_snapshot = btrim(item_name_snapshot)", name="ck_shopping_purchases_name_trimmed"),
        CheckConstraint("char_length(item_name_snapshot) BETWEEN 1 AND 120", name="ck_shopping_purchases_name_length"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    group_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("family_groups.id", ondelete="CASCADE", name="fk_shopping_purchases_group_id_family_groups"),
    )
    trip_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("shopping_trips.id", ondelete="CASCADE", name="fk_shopping_purchases_trip_id_shopping_trips"),
    )
    shopping_item_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("shopping_items.id", ondelete="SET NULL", name="fk_shopping_purchases_item_id_shopping_items"),
        nullable=True,
    )
    item_name_snapshot: Mapped[str] = mapped_column(String(120))
    assignee_user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_shopping_purchases_assignee_user_id_users"),
        nullable=True,
    )
    assignee_username_snapshot: Mapped[str | None] = mapped_column(String(120), nullable=True)
    category_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "shopping_categories.id", ondelete="SET NULL", name="fk_shopping_purchases_category_id_shopping_categories"
        ),
        nullable=True,
    )
    category_name_snapshot: Mapped[str | None] = mapped_column(String(40), nullable=True)
    purchased_by_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_shopping_purchases_purchased_by_user_id_users"),
    )
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_by_user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_shopping_purchases_reversed_by_user_id_users"),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


Index(
    "ix_shopping_items_group_id_purchase_state",
    ShoppingItem.group_id,
    ShoppingItem.purchased_at,
    ShoppingItem.created_at,
)
Index("ix_shopping_items_created_by_user_id", ShoppingItem.created_by_user_id)
Index("ix_shopping_items_purchased_by_user_id", ShoppingItem.purchased_by_user_id)
Index("ix_shopping_items_assignee_user_id", ShoppingItem.assignee_user_id)
Index("ix_shopping_items_category_id", ShoppingItem.category_id)
Index(
    "uq_shopping_categories_group_name_ci",
    ShoppingCategory.group_id,
    func.lower(ShoppingCategory.name),
    unique=True,
)
Index(
    "ix_shopping_categories_group_sort_order",
    ShoppingCategory.group_id,
    ShoppingCategory.sort_order,
    ShoppingCategory.id,
)
Index(
    "ix_shopping_trips_group_started_at", ShoppingTrip.group_id, ShoppingTrip.started_at.desc(), ShoppingTrip.id.desc()
)
Index("ix_shopping_trips_started_by_user_id", ShoppingTrip.started_by_user_id)
Index("ix_shopping_purchases_group_purchased_at", ShoppingPurchase.group_id, ShoppingPurchase.purchased_at.desc())
Index("ix_shopping_purchases_trip_id", ShoppingPurchase.trip_id)
Index("ix_shopping_purchases_item_id", ShoppingPurchase.shopping_item_id)
Index("ix_shopping_purchases_purchased_by_user_id", ShoppingPurchase.purchased_by_user_id)
