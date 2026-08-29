from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.features.auth.dependencies import AuthenticatedUser, require_authenticated_user, require_csrf_token
from app.features.chores.reporting import (
    ChoreMonthlyDaily,
    ChoreMonthlyReport,
    ChoreMonthlyReportInvalidMonthError,
    ChoreMonthlySummary,
)
from app.features.chores.router import (
    complete_chore_task,
    create_chore_category,
    create_chore_task,
    delete_chore_category,
    get_chore_monthly_report,
    list_chore_categories,
    list_chore_tasks,
    reorder_chore_categories,
    update_chore_category,
)
from app.features.chores.schemas import (
    ChoreCategoryCreate,
    ChoreCategoryOrderUpdate,
    ChoreCategoryUpdate,
    ChoreTaskCreate,
)
from app.features.chores.service import (
    ChoreCategoryInUseError,
    ChoreCategoryOrderInvalidError,
    ChoreCategorySummary,
    ChoreForbiddenError,
    ChoreInactiveTaskError,
    ChoreTaskSummary,
)
from app.features.groups.models import GroupRole
from app.main import create_app

TEST_USER = AuthenticatedUser(id=uuid4(), username="owner")


def make_summary() -> ChoreTaskSummary:
    now = datetime(2026, 7, 15, 3, tzinfo=UTC)
    return ChoreTaskSummary(
        id=uuid4(),
        group_id=uuid4(),
        task_name="お風呂",
        category_id=uuid4(),
        interval_days=1,
        is_active=True,
        created_by_user_id=TEST_USER.id,
        created_at=now,
        updated_at=now,
        next_due_at=now,
        current_user_role=GroupRole.ADMIN,
        last_completion=None,
    )


def make_category_summary() -> ChoreCategorySummary:
    now = datetime(2026, 7, 15, 3, tzinfo=UTC)
    return ChoreCategorySummary(id=uuid4(), group_id=uuid4(), name="2階", sort_order=0, created_at=now, updated_at=now)


class ChoreServiceStub:
    def __init__(self, summary: ChoreTaskSummary | None = None, error: Exception | None = None) -> None:
        self.summary = summary
        self.error = error

    def list_tasks(self, group_id: UUID, user_id: UUID) -> list[ChoreTaskSummary]:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        return [self.summary] if self.summary else []

    def create_task(
        self,
        group_id: UUID,
        user_id: UUID,
        name: str,
        interval_days: int,
        category_id: UUID,
    ) -> ChoreTaskSummary:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        assert (name, interval_days, category_id) == ("お風呂", 1, self.summary.category_id)
        assert self.summary is not None
        return self.summary

    def list_categories(self, group_id: UUID, user_id: UUID) -> list[ChoreCategorySummary]:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        return [make_category_summary()]

    def create_category(self, group_id: UUID, user_id: UUID, name: str) -> ChoreCategorySummary:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        return make_category_summary()

    def update_category(self, category_id: UUID, user_id: UUID, name: str) -> ChoreCategorySummary:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        return make_category_summary()

    def reorder_categories(
        self,
        group_id: UUID,
        user_id: UUID,
        category_ids: list[UUID],
    ) -> list[ChoreCategorySummary]:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        return [make_category_summary() for _ in category_ids]

    def delete_category(self, category_id: UUID, user_id: UUID) -> None:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id

    def complete_task(self, task_id: UUID, user_id: UUID) -> ChoreTaskSummary:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        assert self.summary is not None
        return self.summary

    def monthly(self, group_id: UUID, user_id: UUID, month: str) -> ChoreMonthlyReport:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        now = datetime(2026, 8, 1, tzinfo=UTC)
        return ChoreMonthlyReport(
            group_id=group_id,
            month=month,
            timezone="Asia/Tokyo",
            summary=ChoreMonthlySummary(
                completion_count=1,
                unique_task_count=1,
                participant_count=1,
                category_count=1,
            ),
            daily=[ChoreMonthlyDaily(day=now.date(), completion_count=1, unique_task_count=1)],
            categories=[],
            members=[],
            tasks=[],
        )


def test_list_chore_tasks_returns_group_tasks() -> None:
    summary = make_summary()

    response = list_chore_tasks(summary.group_id, TEST_USER, ChoreServiceStub(summary))

    assert response.items[0].id == summary.id


def test_create_chore_task_requires_group_admin() -> None:
    with pytest.raises(HTTPException) as error:
        create_chore_task(
            uuid4(),
            ChoreTaskCreate(task_name="お風呂", interval_days=1, category_id=uuid4()),
            TEST_USER,
            ChoreServiceStub(error=ChoreForbiddenError()),
        )

    assert error.value.status_code == 403


def test_complete_inactive_chore_task_returns_conflict() -> None:
    with pytest.raises(HTTPException) as error:
        complete_chore_task(uuid4(), TEST_USER, ChoreServiceStub(error=ChoreInactiveTaskError()))

    assert error.value.status_code == 409


def test_chore_categories_are_listed_for_group_members() -> None:
    category = make_category_summary()
    service = ChoreServiceStub()

    response = list_chore_categories(category.group_id, TEST_USER, service)

    assert response.items[0].name == "2階"


def test_create_chore_category_requires_csrf_and_returns_category() -> None:
    category = make_category_summary()

    response = create_chore_category(
        category.group_id,
        ChoreCategoryCreate(name="2階"),
        TEST_USER,
        ChoreServiceStub(),
    )

    assert response.name == "2階"


def test_update_chore_category_returns_category() -> None:
    response = update_chore_category(
        uuid4(),
        ChoreCategoryUpdate(name="1階"),
        TEST_USER,
        ChoreServiceStub(),
    )

    assert response.name == "2階"


def test_reorder_chore_categories_returns_ordered_categories() -> None:
    category_ids = [uuid4(), uuid4()]
    response = reorder_chore_categories(
        uuid4(),
        ChoreCategoryOrderUpdate(category_ids=category_ids),
        TEST_USER,
        ChoreServiceStub(),
    )

    assert len(response.items) == 2


def test_reorder_chore_categories_maps_invalid_order() -> None:
    with pytest.raises(HTTPException) as error:
        reorder_chore_categories(
            uuid4(),
            ChoreCategoryOrderUpdate(category_ids=[uuid4()]),
            TEST_USER,
            ChoreServiceStub(error=ChoreCategoryOrderInvalidError()),
        )

    assert error.value.status_code == 422


def test_delete_used_chore_category_returns_conflict() -> None:
    with pytest.raises(HTTPException) as error:
        delete_chore_category(
            uuid4(),
            TEST_USER,
            ChoreServiceStub(error=ChoreCategoryInUseError()),
        )

    assert error.value.status_code == 409


def test_monthly_report_returns_summary() -> None:
    response = get_chore_monthly_report(uuid4(), "2026-08", TEST_USER, ChoreServiceStub())

    assert response.month == "2026-08"
    assert response.summary.completion_count == 1


def test_monthly_report_maps_invalid_month_to_unprocessable_entity() -> None:
    with pytest.raises(HTTPException) as error:
        get_chore_monthly_report(
            uuid4(),
            "2026-08",
            TEST_USER,
            ChoreServiceStub(error=ChoreMonthlyReportInvalidMonthError()),
        )

    assert error.value.status_code == 422


def test_chore_routes_are_registered_and_mutations_require_csrf() -> None:
    paths = create_app(Settings(app_env="test")).openapi()["paths"]

    assert {"get", "post"} <= set(paths["/api/v1/chores/groups/{group_id}/tasks"])
    assert {"get", "post"} <= set(paths["/api/v1/chores/groups/{group_id}/categories"])
    assert "get" in paths["/api/v1/chores/groups/{group_id}/reports/monthly"]
    assert {"get", "patch"} <= set(paths["/api/v1/chores/tasks/{task_id}"])
    assert {"patch", "delete"} <= set(paths["/api/v1/chores/categories/{category_id}"])
    assert "post" in paths["/api/v1/chores/tasks/{task_id}/completions"]

    from app.features.chores.router import router

    assert any(dependency.dependency is require_authenticated_user for dependency in router.dependencies)
    mutation_routes = [route for route in router.routes if route.methods & {"POST", "PATCH", "DELETE"}]
    assert mutation_routes
    assert all(
        any(dependency.dependency is require_csrf_token for dependency in route.dependencies)
        for route in mutation_routes
    )
