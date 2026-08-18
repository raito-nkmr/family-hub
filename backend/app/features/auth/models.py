from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
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
        CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="ck_user_sessions_token_hash_lower_hex"),
        CheckConstraint("csrf_token ~ '^[A-Za-z0-9_-]{43}$'", name="ck_user_sessions_csrf_token"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_user_sessions_user_id_users"),
    )
    token_hash: Mapped[str] = mapped_column(String(64))
    csrf_token: Mapped[str] = mapped_column(String(43))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()


class UserInvitation(Base):
    __tablename__ = "user_invitations"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_user_invitations"),
        UniqueConstraint("token_hash", name="uq_user_invitations_token_hash"),
        CheckConstraint("username = lower(username)", name="ck_user_invitations_username_lowercase"),
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


Index("ix_user_sessions_user_id", UserSession.user_id)
Index("ix_user_invitations_created_at", UserInvitation.created_at.desc(), UserInvitation.id.desc())
Index(
    "uq_user_invitations_pending_username",
    UserInvitation.username,
    unique=True,
    postgresql_where=UserInvitation.used_at.is_(None) & UserInvitation.revoked_at.is_(None),
)
