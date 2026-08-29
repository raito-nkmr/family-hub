from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class SystemRole(StrEnum):
    ADMIN = "admin"
    USER = "user"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_users"),
        UniqueConstraint("username", name="uq_users_username"),
        CheckConstraint("username = lower(username)", name="ck_users_username_lowercase"),
        CheckConstraint("username = btrim(username)", name="ck_users_username_trimmed"),
        CheckConstraint("char_length(username) BETWEEN 1 AND 64", name="ck_users_username_length"),
        CheckConstraint("system_role IN ('admin', 'user')", name="ck_users_system_role"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    username: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    system_role: Mapped[str] = mapped_column(String(16), default=SystemRole.USER, server_default=SystemRole.USER)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
    )
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_user_sessions"),
        UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
        UniqueConstraint("id", "user_id", name="uq_user_sessions_id_user_id"),
        CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="ck_user_sessions_token_hash_lower_hex"),
        CheckConstraint("csrf_token ~ '^[A-Za-z0-9_-]{43}$'", name="ck_user_sessions_csrf_token"),
        CheckConstraint("expires_at > created_at", name="ck_user_sessions_expires_after_created"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_user_sessions_user_id_users"),
    )
    token_hash: Mapped[str] = mapped_column(String(64))
    csrf_token: Mapped[str] = mapped_column(String(43))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()


class UserInvitation(Base):
    __tablename__ = "user_invitations"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_user_invitations"),
        UniqueConstraint("token_hash", name="uq_user_invitations_token_hash"),
        CheckConstraint("username = lower(username)", name="ck_user_invitations_username_lowercase"),
        CheckConstraint("username = btrim(username)", name="ck_user_invitations_username_trimmed"),
        CheckConstraint("char_length(username) BETWEEN 1 AND 64", name="ck_user_invitations_username_length"),
        CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="ck_user_invitations_token_hash_lower_hex"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    username: Mapped[str] = mapped_column(String(64))
    token_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_user_invitations_created_by_user_id_users"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginRateLimit(Base):
    __tablename__ = "login_rate_limits"
    __table_args__ = (
        PrimaryKeyConstraint("key_hash", name="pk_login_rate_limits"),
        CheckConstraint("key_hash ~ '^[0-9a-f]{64}$'", name="ck_login_rate_limits_key_hash_lower_hex"),
        CheckConstraint("attempt_count >= 0", name="ck_login_rate_limits_attempt_count_nonnegative"),
    )

    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


Index("ix_user_sessions_user_id", UserSession.user_id)
Index("ix_user_invitations_created_at", UserInvitation.created_at.desc(), UserInvitation.id.desc())
Index("ix_login_rate_limits_updated_at", LoginRateLimit.updated_at)
Index(
    "uq_user_invitations_pending_username",
    UserInvitation.username,
    unique=True,
    postgresql_where=UserInvitation.used_at.is_(None) & UserInvitation.revoked_at.is_(None),
)
