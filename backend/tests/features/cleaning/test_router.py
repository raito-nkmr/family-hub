from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.features.auth.dependencies import AuthenticatedUser, require_authenticated_user, require_csrf_token
from app.features.cleaning.router import complete_cleaning_task, create_cleaning_task, list_cleaning_tasks
from app.features.cleaning.schemas import CleaningTaskCreate
from app.features.cleaning.service import (
    CleaningForbiddenError,
    CleaningInactiveTaskError,
    CleaningTaskSummary,
)
from app.features.groups.models import GroupRole
from app.main import create_app

TEST_USER = AuthenticatedUser(id=uuid4(), username="owner")


def make_summary() -> CleaningTaskSummary:
    now = datetime(2026, 7, 15, 3, tzinfo=UTC)
    return CleaningTaskSummary(
        id=uuid4(),
        group_id=uuid4(),
        name="お風呂",
        interval_days=1,
        is_active=True,
        created_by_user_id=TEST_USER.id,
        created_at=now,
        updated_at=now,
        next_due_at=now,
        current_user_role=GroupRole.ADMIN,
        last_completion=None,
    )


class CleaningServiceStub:
    def __init__(self, summary: CleaningTaskSummary | None = None, error: Exception | None = None) -> None:
        self.summary = summary
        self.error = error

    def list_tasks(self, group_id: UUID, user_id: UUID) -> list[CleaningTaskSummary]:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        return [self.summary] if self.summary else []

    def create_task(self, group_id: UUID, user_id: UUID, name: str, interval_days: int) -> CleaningTaskSummary:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        assert (name, interval_days) == ("お風呂", 1)
        assert self.summary is not None
        return self.summary

    def complete_task(self, task_id: UUID, user_id: UUID) -> CleaningTaskSummary:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        assert self.summary is not None
        return self.summary


def test_list_cleaning_tasks_returns_group_tasks() -> None:
    summary = make_summary()

    response = list_cleaning_tasks(summary.group_id, TEST_USER, CleaningServiceStub(summary))

    assert response.items[0].id == summary.id


def test_create_cleaning_task_requires_group_admin() -> None:
    with pytest.raises(HTTPException) as error:
        create_cleaning_task(
            uuid4(),
            CleaningTaskCreate(name="お風呂", interval_days=1),
            TEST_USER,
            CleaningServiceStub(error=CleaningForbiddenError()),
        )

    assert error.value.status_code == 403


def test_complete_inactive_cleaning_task_returns_conflict() -> None:
    with pytest.raises(HTTPException) as error:
        complete_cleaning_task(uuid4(), TEST_USER, CleaningServiceStub(error=CleaningInactiveTaskError()))

    assert error.value.status_code == 409


def test_cleaning_routes_are_registered_and_mutations_require_csrf() -> None:
    paths = create_app(Settings(app_env="test")).openapi()["paths"]

    assert {"get", "post"} <= set(paths["/api/v1/cleaning/groups/{group_id}/tasks"])
    assert {"get", "patch"} <= set(paths["/api/v1/cleaning/tasks/{task_id}"])
    assert "post" in paths["/api/v1/cleaning/tasks/{task_id}/completions"]

    from app.features.cleaning.router import router

    assert any(dependency.dependency is require_authenticated_user for dependency in router.dependencies)
    mutation_routes = [route for route in router.routes if route.methods & {"POST", "PATCH", "DELETE"}]
    assert mutation_routes
    assert all(
        any(dependency.dependency is require_csrf_token for dependency in route.dependencies)
        for route in mutation_routes
    )
