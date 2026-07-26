from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, PrimaryKeyConstraint, String, func
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


Index(
    "ix_shopping_items_group_id_purchase_state",
    ShoppingItem.group_id,
    ShoppingItem.purchased_at,
    ShoppingItem.created_at,
)
