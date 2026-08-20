from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.features.auth.public import PublicUser, UserDirectory
from app.features.groups.models import FamilyGroup, FamilyGroupMember, FamilyGroupMembershipInvitation, GroupRole
from app.features.groups.service import (
    GroupForbiddenError,
    GroupMembershipInvitationError,
    GroupNameAlreadyExistsError,
    GroupNotFoundError,
    GroupPersistenceError,
    GroupService,
    LastGroupAdminError,
)
from tests.features.groups.factories import make_group, make_membership


def make_service(session: Session) -> tuple[GroupService, MagicMock]:
    directory = MagicMock(spec=UserDirectory)
    return GroupService(session, directory), directory


def test_list_groups_returns_only_memberships_in_expected_order() -> None:
    session = MagicMock(spec=Session)
    group = make_group()
    session.execute.return_value.__iter__.return_value = iter([(group, GroupRole.ADMIN, 3)])
    service, _ = make_service(session)
    user_id = uuid4()

    result = service.list_groups(user_id)

    assert result[0].id == group.id
    assert result[0].current_user_role is GroupRole.ADMIN
    assert result[0].member_count == 3
    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "family_group_members" in sql
    assert "ORDER BY family_groups.updated_at DESC, family_groups.id DESC" in sql


def test_get_group_returns_members_for_group_member() -> None:
    session = MagicMock(spec=Session)
    user_id = uuid4()
    group = make_group(created_by_user_id=user_id)
    membership = make_membership(group.id, user_id)
    session.execute.return_value.one_or_none.return_value = (group, GroupRole.ADMIN)
    session.scalars.return_value.all.return_value = [membership]
    service, directory = make_service(session)
    directory.list_by_ids.return_value = {
        user_id: PublicUser(id=user_id, username="owner", is_active=True),
    }

    result = service.get_group(group.id, user_id)

    assert result.group.member_count == 1
    assert result.members[0].username == "owner"
    assert result.members[0].role is GroupRole.ADMIN


def test_get_group_hides_group_from_non_member() -> None:
    session = MagicMock(spec=Session)
    session.execute.return_value.one_or_none.return_value = None
    service, _ = make_service(session)

    with pytest.raises(GroupNotFoundError):
        service.get_group(uuid4(), uuid4())


def test_create_group_adds_creator_as_admin() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    creator_id = uuid4()
    service, directory = make_service(session)
    directory.list_by_ids.return_value = {
        creator_id: PublicUser(id=creator_id, username="owner", is_active=True),
    }

    result = service.create_group("同居家族", creator_id)

    group, membership = session.add_all.call_args.args[0]
    assert isinstance(group, FamilyGroup)
    assert isinstance(membership, FamilyGroupMember)
    assert membership.group_id == group.id
    assert membership.user_id == creator_id
    assert membership.role is GroupRole.ADMIN
    assert result.group.current_user_role is GroupRole.ADMIN
    assert result.members[0].username == "owner"
    session.commit.assert_called_once_with()


def test_create_group_rejects_existing_name() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = uuid4()
    service, _ = make_service(session)

    with pytest.raises(GroupNameAlreadyExistsError):
        service.create_group("同居家族", uuid4())

    session.add_all.assert_not_called()
    session.commit.assert_not_called()


def test_create_group_maps_unique_constraint_race_to_existing_name() -> None:
    class Diagnostic:
        constraint_name = "uq_family_groups_name"

    class UniqueViolation(Exception):
        diag = Diagnostic()

    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    session.commit.side_effect = IntegrityError("insert", {}, UniqueViolation())
    service, _ = make_service(session)

    with pytest.raises(GroupNameAlreadyExistsError):
        service.create_group("同居家族", uuid4())

    session.rollback.assert_called_once_with()


def test_create_group_rolls_back_on_persistence_failure() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    session.commit.side_effect = OperationalError("commit", {}, RuntimeError("database unavailable"))
    service, _ = make_service(session)

    with pytest.raises(GroupPersistenceError):
        service.create_group("同居家族", uuid4())

    session.rollback.assert_called_once_with()


def test_rename_group_wraps_unexpected_database_errors() -> None:
    session = MagicMock(spec=Session)
    actor_id = uuid4()
    group = make_group(created_by_user_id=actor_id)
    session.scalar.return_value = group
    session.get.return_value = make_membership(group.id, actor_id)
    session.commit.side_effect = OperationalError("commit", {}, RuntimeError("database unavailable"))
    service, directory = make_service(session)
    directory.list_by_ids.return_value = {
        actor_id: PublicUser(id=actor_id, username="owner", is_active=True),
    }

    with pytest.raises(GroupPersistenceError):
        service.rename_group(group.id, actor_id, "owner", "新しい名前")

    session.rollback.assert_called_once_with()


def test_invite_member_wraps_unexpected_database_errors() -> None:
    session = MagicMock(spec=Session)
    actor_id = uuid4()
    target_id = uuid4()
    group = make_group(created_by_user_id=actor_id)
    session.scalar.return_value = group
    session.get.side_effect = [make_membership(group.id, actor_id), None]
    session.commit.side_effect = OperationalError("commit", {}, RuntimeError("database unavailable"))
    service, directory = make_service(session)
    directory.list_by_ids.side_effect = [
        {actor_id: PublicUser(id=actor_id, username="owner", is_active=True)},
        {target_id: PublicUser(id=target_id, username="たろう", is_active=True)},
    ]

    with pytest.raises(GroupPersistenceError):
        service.invite_member(group.id, actor_id, "owner", target_id, GroupRole.MEMBER)

    session.rollback.assert_called_once_with()


def test_list_member_candidates_returns_active_non_members() -> None:
    session = MagicMock(spec=Session)
    actor_id = uuid4()
    candidate_id = uuid4()
    group = make_group(created_by_user_id=actor_id)
    session.scalar.return_value = group
    session.get.return_value = make_membership(group.id, actor_id)
    session.scalars.return_value.all.return_value = [actor_id]
    service, directory = make_service(session)
    candidate = PublicUser(id=candidate_id, username="たろう", is_active=True)
    directory.list_active.return_value = [
        PublicUser(id=actor_id, username="owner", is_active=True),
        candidate,
    ]

    result = service.list_member_candidates(group.id, actor_id)

    assert result == [candidate]


def test_accept_membership_invitation_locks_group_before_invitation_and_adds_member() -> None:
    session = MagicMock(spec=Session)
    user_id = uuid4()
    group = make_group()
    invitation = FamilyGroupMembershipInvitation(
        id=uuid4(),
        group_id=group.id,
        user_id=user_id,
        requested_by_user_id=uuid4(),
        role=GroupRole.MEMBER,
        status="pending",
        created_at=group.created_at,
        responded_at=None,
    )
    session.scalar.side_effect = [invitation, group, invitation]
    session.get.return_value = None
    service, _ = make_service(session)

    service.decide_membership_invitation(invitation.id, user_id, "member", True)

    statements = [call.args[0] for call in session.scalar.call_args_list]
    assert "FOR UPDATE" not in str(statements[0])
    assert "family_groups.id" in str(statements[1])
    assert "FOR UPDATE" in str(statements[1])
    assert "family_group_membership_invitations.id" in str(statements[2])
    assert "FOR UPDATE" in str(statements[2])
    memberships = [call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], FamilyGroupMember)]
    assert len(memberships) == 1
    assert memberships[0].user_id == user_id
    session.commit.assert_called_once_with()


def test_accept_membership_invitation_does_not_insert_existing_member() -> None:
    session = MagicMock(spec=Session)
    user_id = uuid4()
    group = make_group()
    invitation = FamilyGroupMembershipInvitation(
        id=uuid4(),
        group_id=group.id,
        user_id=user_id,
        requested_by_user_id=uuid4(),
        role=GroupRole.MEMBER,
        status="pending",
        created_at=group.created_at,
        responded_at=None,
    )
    session.scalar.side_effect = [invitation, group, invitation]
    session.get.return_value = make_membership(group.id, user_id)
    service, _ = make_service(session)

    service.decide_membership_invitation(invitation.id, user_id, "member", True)

    assert not any(isinstance(call.args[0], FamilyGroupMember) for call in session.add.call_args_list)
    assert invitation.status == "accepted"
    session.commit.assert_called_once_with()


def test_accept_membership_invitation_rejects_missing_pending_invitation() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    service, _ = make_service(session)

    with pytest.raises(GroupMembershipInvitationError):
        service.decide_membership_invitation(uuid4(), uuid4(), "member", True)

    session.commit.assert_not_called()


def test_member_cannot_manage_group_memberships() -> None:
    session = MagicMock(spec=Session)
    actor_id = uuid4()
    group = make_group()
    actor_membership = make_membership(group.id, actor_id, role=GroupRole.MEMBER)
    session.scalar.return_value = group
    session.get.return_value = actor_membership
    service, _ = make_service(session)

    with pytest.raises(GroupForbiddenError):
        service.remove_member(group.id, actor_id, actor_id)

    session.delete.assert_not_called()


def test_update_role_prevents_demoting_last_active_admin() -> None:
    session = MagicMock(spec=Session)
    actor_id = uuid4()
    group = make_group(created_by_user_id=actor_id)
    actor_membership = make_membership(group.id, actor_id)
    session.scalar.return_value = group
    session.get.side_effect = [actor_membership, actor_membership]
    session.scalars.return_value.all.return_value = [actor_membership]
    service, directory = make_service(session)
    directory.list_by_ids.return_value = {
        actor_id: PublicUser(id=actor_id, username="owner", is_active=True),
    }

    with pytest.raises(LastGroupAdminError):
        service.update_member_role(group.id, actor_id, actor_id, GroupRole.MEMBER)

    session.commit.assert_not_called()


def test_inactive_admin_does_not_satisfy_last_active_admin_rule() -> None:
    session = MagicMock(spec=Session)
    actor_id = uuid4()
    inactive_admin_id = uuid4()
    group = make_group(created_by_user_id=actor_id)
    actor_membership = make_membership(group.id, actor_id)
    inactive_admin_membership = make_membership(group.id, inactive_admin_id)
    session.scalar.return_value = group
    session.get.side_effect = [actor_membership, actor_membership]
    session.scalars.return_value.all.return_value = [actor_membership, inactive_admin_membership]
    service, directory = make_service(session)
    directory.list_by_ids.return_value = {
        actor_id: PublicUser(id=actor_id, username="owner", is_active=True),
        inactive_admin_id: PublicUser(id=inactive_admin_id, username="inactive", is_active=False),
    }

    with pytest.raises(LastGroupAdminError):
        service.update_member_role(group.id, actor_id, actor_id, GroupRole.MEMBER)

    session.commit.assert_not_called()


def test_update_role_allows_demoting_admin_when_another_active_admin_exists() -> None:
    session = MagicMock(spec=Session)
    actor_id = uuid4()
    target_id = uuid4()
    group = make_group(created_by_user_id=actor_id)
    actor_membership = make_membership(group.id, actor_id)
    target_membership = make_membership(group.id, target_id)
    session.scalar.return_value = group
    session.get.side_effect = [actor_membership, target_membership]
    session.scalars.return_value.all.return_value = [actor_membership, target_membership]
    service, directory = make_service(session)
    directory.list_by_ids.return_value = {
        actor_id: PublicUser(id=actor_id, username="owner", is_active=True),
        target_id: PublicUser(id=target_id, username="other-admin", is_active=True),
    }
    expected = object()
    service.get_group = MagicMock(return_value=expected)

    result = service.update_member_role(group.id, target_id, actor_id, GroupRole.MEMBER)

    assert target_membership.role is GroupRole.MEMBER
    assert result is expected
    session.commit.assert_called_once_with()


def test_remove_member_prevents_removing_last_active_admin() -> None:
    session = MagicMock(spec=Session)
    actor_id = uuid4()
    group = make_group(created_by_user_id=actor_id)
    actor_membership = make_membership(group.id, actor_id)
    session.scalar.return_value = group
    session.get.side_effect = [actor_membership, actor_membership]
    session.scalars.return_value.all.return_value = [actor_membership]
    service, directory = make_service(session)
    directory.list_by_ids.return_value = {
        actor_id: PublicUser(id=actor_id, username="owner", is_active=True),
    }

    with pytest.raises(LastGroupAdminError):
        service.remove_member(group.id, actor_id, actor_id)

    session.delete.assert_not_called()
