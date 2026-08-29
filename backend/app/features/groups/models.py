from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class GroupRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"


class FamilyGroup(Base):
    __tablename__ = "family_groups"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_family_groups"),
        UniqueConstraint("name", name="uq_family_groups_name"),
        CheckConstraint("name = btrim(name)", name="ck_family_groups_name_trimmed"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 120", name="ck_family_groups_name_length"),
        CheckConstraint("timezone = btrim(timezone)", name="ck_family_groups_timezone_trimmed"),
        CheckConstraint("char_length(timezone) BETWEEN 1 AND 64", name="ck_family_groups_timezone_length"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64), server_default="Asia/Tokyo")
    created_by_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_family_groups_created_by_user_id_users"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class FamilyGroupMember(Base):
    __tablename__ = "family_group_members"
    __table_args__ = (
        PrimaryKeyConstraint("group_id", "user_id", name="pk_family_group_members"),
        CheckConstraint("role IN ('admin', 'member')", name="ck_family_group_members_role"),
    )

    group_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("family_groups.id", ondelete="CASCADE", name="fk_family_group_members_group_id_family_groups"),
        primary_key=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_family_group_members_user_id_users"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(16))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class FamilyGroupMembershipInvitation(Base):
    __tablename__ = "family_group_membership_invitations"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_family_group_membership_invitations"),
        CheckConstraint("role IN ('admin', 'member')", name="ck_family_group_membership_invitations_role"),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'canceled')",
            name="ck_family_group_membership_invitations_status",
        ),
        CheckConstraint(
            "(status = 'pending' AND responded_at IS NULL) OR (status <> 'pending' AND responded_at IS NOT NULL)",
            name="ck_family_group_membership_invitations_responded_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    group_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "family_groups.id",
            ondelete="CASCADE",
            name="fk_family_group_membership_invitations_group_id_family_groups",
        ),
    )
    invitee_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_family_group_membership_invitations_invitee_user_id_users"),
    )
    invited_by_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
            name="fk_family_group_membership_invitations_invited_by_user_id_users",
        ),
    )
    role: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index("ix_family_groups_created_by_user_id", FamilyGroup.created_by_user_id)
Index("ix_family_group_members_user_id", FamilyGroupMember.user_id)
Index(
    "uq_family_group_membership_invitations_pending",
    FamilyGroupMembershipInvitation.group_id,
    FamilyGroupMembershipInvitation.invitee_user_id,
    unique=True,
    postgresql_where=FamilyGroupMembershipInvitation.status == "pending",
)
Index("ix_family_group_membership_invitations_group_id", FamilyGroupMembershipInvitation.group_id)
Index(
    "ix_family_group_membership_invitations_invited_by_user_id",
    FamilyGroupMembershipInvitation.invited_by_user_id,
)
Index(
    "ix_family_group_membership_invitations_invitee_status",
    FamilyGroupMembershipInvitation.invitee_user_id,
    FamilyGroupMembershipInvitation.status,
)
