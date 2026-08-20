from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.features.auth.dependencies import AuthenticatedUser, require_authenticated_user, require_csrf_token
from app.features.auth.public import PublicUser
from app.features.groups.models import GroupRole
from app.features.groups.router import (
    create_group,
    get_group,
    list_group_member_candidates,
    list_groups,
    remove_group_member,
    rename_group,
    update_group_member_role,
)
from app.features.groups.schemas import GroupCreate, GroupMemberRoleUpdate, GroupUpdate
from app.features.groups.service import (
    GroupDetail,
    GroupMemberSummary,
    GroupNameAlreadyExistsError,
    GroupNotFoundError,
    GroupPersistenceError,
    GroupSummary,
    LastGroupAdminError,
)
from app.main import create_app

TEST_USER = AuthenticatedUser(id=uuid4(), username="owner")
TEST_TARGET_USER_ID = uuid4()


def make_detail() -> GroupDetail:
    now = datetime(2026, 7, 15, 3, tzinfo=UTC)
    group = GroupSummary(
        id=uuid4(),
        name="同居家族",
        created_by_user_id=TEST_USER.id,
        created_at=now,
        updated_at=now,
        current_user_role=GroupRole.ADMIN,
        member_count=1,
    )
    member = GroupMemberSummary(
        user_id=TEST_USER.id,
        username=TEST_USER.username,
        is_active=True,
        role=GroupRole.ADMIN,
        joined_at=now,
    )
    return GroupDetail(group=group, members=[member])


class GroupServiceStub:
    def __init__(self, detail: GroupDetail | None = None, error: Exception | None = None) -> None:
        self.detail = detail
        self.error = error

    def list_groups(self, user_id: UUID) -> list[GroupSummary]:
        assert user_id == TEST_USER.id
        return [self.detail.group] if self.detail else []

    def create_group(
        self,
        name: str,
        creator_user_id: UUID,
        creator_username: str = "unknown",
    ) -> GroupDetail:
        if self.error:
            raise self.error
        assert name == "同居家族"
        assert creator_user_id == TEST_USER.id
        assert self.detail is not None
        return self.detail

    def get_group(self, group_id: UUID, user_id: UUID) -> GroupDetail:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        assert self.detail is not None
        return self.detail

    def rename_group(self, group_id: UUID, actor_user_id: UUID, actor_username: str, name: str) -> GroupDetail:
        if self.error:
            raise self.error
        assert actor_user_id == TEST_USER.id
        assert name == "新しい名前"
        assert self.detail is not None
        return self.detail

    def list_member_candidates(self, group_id: UUID, actor_user_id: UUID) -> list[PublicUser]:
        if self.error:
            raise self.error
        assert actor_user_id == TEST_USER.id
        return [PublicUser(id=TEST_TARGET_USER_ID, username="たろう", is_active=True)]

    def update_member_role(
        self,
        group_id: UUID,
        target_user_id: UUID,
        actor_user_id: UUID,
        role: GroupRole,
        actor_username: str,
    ) -> GroupDetail:
        if self.error:
            raise self.error
        assert actor_user_id == TEST_USER.id
        assert role is GroupRole.MEMBER
        assert self.detail is not None
        return self.detail

    def remove_member(
        self,
        group_id: UUID,
        target_user_id: UUID,
        actor_user_id: UUID,
        actor_username: str,
    ) -> None:
        if self.error:
            raise self.error
        assert actor_user_id == TEST_USER.id


def test_list_groups_returns_memberships() -> None:
    detail = make_detail()

    response = list_groups(TEST_USER, GroupServiceStub(detail))

    assert response.items[0].id == detail.group.id


def test_create_group_returns_creator_membership() -> None:
    detail = make_detail()

    response = create_group(GroupCreate(name="同居家族"), TEST_USER, GroupServiceStub(detail))

    assert response.id == detail.group.id
    assert response.members[0].role is GroupRole.ADMIN


def test_create_group_maps_existing_name_to_conflict() -> None:
    with pytest.raises(HTTPException) as error:
        create_group(
            GroupCreate(name="同居家族"),
            TEST_USER,
            GroupServiceStub(error=GroupNameAlreadyExistsError()),
        )

    assert error.value.status_code == 409
    assert error.value.detail == "Group name already exists"


def test_get_group_maps_non_member_to_404() -> None:
    group_id = uuid4()

    with pytest.raises(HTTPException) as error:
        get_group(group_id, TEST_USER, GroupServiceStub(error=GroupNotFoundError(group_id)))

    assert error.value.status_code == 404
    assert error.value.detail == "Group not found"


def test_rename_group_maps_persistence_error_to_500() -> None:
    with pytest.raises(HTTPException) as error:
        rename_group(
            uuid4(),
            GroupUpdate(name="新しい名前"),
            TEST_USER,
            GroupServiceStub(error=GroupPersistenceError()),
        )

    assert error.value.status_code == 500


def test_list_group_member_candidates_returns_selectable_users() -> None:
    response = list_group_member_candidates(uuid4(), TEST_USER, GroupServiceStub())

    assert response.items[0].user_id == TEST_TARGET_USER_ID
    assert response.items[0].username == "たろう"


def test_update_group_member_role_protects_last_admin() -> None:
    detail = make_detail()

    with pytest.raises(HTTPException) as error:
        update_group_member_role(
            detail.group.id,
            TEST_USER.id,
            GroupMemberRoleUpdate(role=GroupRole.MEMBER),
            TEST_USER,
            GroupServiceStub(error=LastGroupAdminError()),
        )

    assert error.value.status_code == 409


def test_remove_group_member_returns_no_content() -> None:
    response = remove_group_member(uuid4(), uuid4(), TEST_USER, GroupServiceStub())

    assert response.status_code == 204


def test_group_routes_are_registered_and_mutations_require_csrf() -> None:
    paths = create_app(Settings(app_env="test")).openapi()["paths"]

    assert {"get", "post"} <= set(paths["/api/v1/groups"])
    assert "get" in paths["/api/v1/groups/{group_id}"]
    assert "get" in paths["/api/v1/groups/{group_id}/member-candidates"]
    assert "/api/v1/groups/{group_id}/members" not in paths
    assert {"patch", "delete"} <= set(paths["/api/v1/groups/{group_id}/members/{user_id}"])

    from app.features.groups.router import router

    assert any(dependency.dependency is require_authenticated_user for dependency in router.dependencies)
    mutation_routes = [route for route in router.routes if route.methods & {"POST", "PATCH", "DELETE"}]
    assert mutation_routes
    assert all(
        any(dependency.dependency is require_csrf_token for dependency in route.dependencies)
        for route in mutation_routes
    )
