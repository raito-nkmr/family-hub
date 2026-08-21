from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.features.groups.models import FamilyGroup, FamilyGroupMember, GroupRole


def make_group(group_id: UUID | None = None, *, created_by_user_id: UUID | None = None) -> FamilyGroup:
    now = datetime(2026, 7, 15, 3, tzinfo=UTC)
    return FamilyGroup(
        id=group_id or uuid4(),
        name="同居家族",
        timezone="Asia/Tokyo",
        created_by_user_id=created_by_user_id or uuid4(),
        created_at=now,
        updated_at=now,
    )


def make_membership(
    group_id: UUID,
    user_id: UUID,
    *,
    role: GroupRole = GroupRole.ADMIN,
) -> FamilyGroupMember:
    return FamilyGroupMember(
        group_id=group_id,
        user_id=user_id,
        role=role,
        joined_at=datetime(2026, 7, 15, 3, tzinfo=UTC),
    )
