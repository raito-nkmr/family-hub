from collections.abc import Collection
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.groups.models import FamilyGroup, FamilyGroupMember, GroupRole

__all__ = [
    "FamilyGroup",
    "FamilyGroupMember",
    "GroupRole",
    "get_user_group_ids",
    "lock_group_admin",
    "lock_user_group_ids",
]


def get_user_group_ids(session: Session, user_id: UUID, requested_ids: Collection[UUID]) -> set[UUID]:
    if not requested_ids:
        return set()
    statement = select(FamilyGroupMember.group_id).where(
        FamilyGroupMember.user_id == user_id,
        FamilyGroupMember.group_id.in_(requested_ids),
    )
    return set(session.scalars(statement).all())


def lock_user_group_ids(session: Session, user_id: UUID, requested_ids: Collection[UUID]) -> set[UUID]:
    """Lock requested groups while confirming membership for an authorization-sensitive commit."""
    if not requested_ids:
        return set()
    statement = (
        select(FamilyGroup.id)
        .join(FamilyGroupMember, FamilyGroupMember.group_id == FamilyGroup.id)
        .where(
            FamilyGroup.id.in_(requested_ids),
            FamilyGroupMember.user_id == user_id,
        )
        .order_by(FamilyGroup.id)
        .with_for_update(of=FamilyGroup)
    )
    return set(session.scalars(statement).all())


def lock_group_admin(session: Session, group_id: UUID, user_id: UUID) -> FamilyGroup | None:
    group = session.scalar(select(FamilyGroup).where(FamilyGroup.id == group_id).with_for_update())
    membership = session.get(FamilyGroupMember, (group_id, user_id)) if group is not None else None
    if membership is None or GroupRole(membership.role) is not GroupRole.ADMIN:
        return None
    return group
