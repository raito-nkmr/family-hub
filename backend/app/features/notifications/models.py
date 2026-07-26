from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class NotificationType(StrEnum):
    PHOTO_SHARED = "photo_shared"
    CLEANING_DUE = "cleaning_due"
    SHOPPING_ADDED = "shopping_added"


class NotificationOutboxStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"


class NotificationDeliveryStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_push_subscriptions"),
        UniqueConstraint("endpoint_hash", name="uq_push_subscriptions_endpoint_hash"),
        CheckConstraint("locale IN ('en', 'ja')", name="ck_push_subscriptions_locale"),
        CheckConstraint("failure_count >= 0", name="ck_push_subscriptions_failure_count"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_push_subscriptions_user_id_users"),
    )
    user_session_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("user_sessions.id", ondelete="CASCADE", name="fk_push_subscriptions_user_session_id_user_sessions"),
    )
    endpoint_hash: Mapped[str] = mapped_column(String(64))
    endpoint: Mapped[str] = mapped_column(Text)
    p256dh_key: Mapped[str] = mapped_column(Text)
    auth_key: Mapped[str] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(String(2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


Index("ix_push_subscriptions_user_id", PushSubscription.user_id)
Index("ix_push_subscriptions_user_session_id", PushSubscription.user_session_id)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "notification_type", name="pk_notification_preferences"),
        CheckConstraint(
            "notification_type IN ('photo_shared', 'cleaning_due', 'shopping_added')",
            name="ck_notification_preferences_type",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_notification_preferences_user_id_users"),
        primary_key=True,
    )
    notification_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_notification_outbox"),
        UniqueConstraint("recipient_user_id", "deduplication_key", name="uq_notification_outbox_recipient_dedupe"),
        CheckConstraint(
            "notification_type IN ('photo_shared', 'cleaning_due', 'shopping_added')",
            name="ck_notification_outbox_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'sent', 'failed')",
            name="ck_notification_outbox_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_notification_outbox_attempt_count"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    recipient_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_notification_outbox_recipient_user_id_users"),
    )
    notification_type: Mapped[str] = mapped_column(String(32))
    deduplication_key: Mapped[str] = mapped_column(String(160))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default=NotificationOutboxStatus.PENDING)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_token: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    last_error: Mapped[str | None] = mapped_column(String(128))


Index("ix_notification_outbox_pending", NotificationOutbox.status, NotificationOutbox.available_at)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        PrimaryKeyConstraint("outbox_id", "subscription_id", name="pk_notification_deliveries"),
        ForeignKeyConstraint(
            ["outbox_id"],
            ["notification_outbox.id"],
            name="fk_notification_deliveries_outbox_id_notification_outbox",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["subscription_id"],
            ["push_subscriptions.id"],
            name="fk_notification_deliveries_subscription_id_push_subscriptions",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('pending', 'sent', 'failed')",
            name="ck_notification_deliveries_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_notification_deliveries_attempt_count"),
    )

    outbox_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    subscription_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default=NotificationDeliveryStatus.PENDING)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(128))
