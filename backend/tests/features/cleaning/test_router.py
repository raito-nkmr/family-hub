from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.features.auth.dependencies import AuthenticatedUser, require_authenticated_user, require_csrf_token
from app.features.cleaning.reporting import (
    CleaningMonthlyDaily,
    CleaningMonthlyReport,
    CleaningMonthlySummary,
    CleaningReportInvalidMonthError,
)
from app.features.cleaning.router import (
    complete_cleaning_task,
    create_cleaning_category,
    create_cleaning_task,
    delete_cleaning_category,
    get_cleaning_monthly_report,
    list_cleaning_categories,
    list_cleaning_tasks,
    reorder_cleaning_categories,
    update_cleaning_category,
)
from app.features.cleaning.schemas import (
    CleaningCategoryCreate,
    CleaningCategoryOrderUpdate,
    CleaningCategoryUpdate,
    CleaningTaskCreate,
)
from app.features.cleaning.service import (
    CleaningCategoryInUseError,
    CleaningCategoryOrderInvalidError,
    CleaningCategorySummary,
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


def make_category_summary() -> CleaningCategorySummary:
    now = datetime(2026, 7, 15, 3, tzinfo=UTC)
    return CleaningCategorySummary(
        id=uuid4(), group_id=uuid4(), name="2階", sort_order=0, created_at=now, updated_at=now
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

    def create_task(
        self,
        group_id: UUID,
        user_id: UUID,
        name: str,
        interval_days: int,
        category_id: UUID,
    ) -> CleaningTaskSummary:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        assert (name, interval_days, category_id) == ("お風呂", 1, self.summary.category_id)
        assert self.summary is not None
        return self.summary

    def list_categories(self, group_id: UUID, user_id: UUID) -> list[CleaningCategorySummary]:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        return [make_category_summary()]

    def create_category(self, group_id: UUID, user_id: UUID, name: str) -> CleaningCategorySummary:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        return make_category_summary()

    def update_category(self, category_id: UUID, user_id: UUID, name: str) -> CleaningCategorySummary:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        return make_category_summary()

    def reorder_categories(
        self,
        group_id: UUID,
        user_id: UUID,
        category_ids: list[UUID],
    ) -> list[CleaningCategorySummary]:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        return [make_category_summary() for _ in category_ids]

    def delete_category(self, category_id: UUID, user_id: UUID) -> None:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id

    def complete_task(self, task_id: UUID, user_id: UUID) -> CleaningTaskSummary:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        assert self.summary is not None
        return self.summary

    def monthly(self, group_id: UUID, user_id: UUID, month: str) -> CleaningMonthlyReport:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        now = datetime(2026, 8, 1, tzinfo=UTC)
        return CleaningMonthlyReport(
            group_id=group_id,
            month=month,
            timezone="Asia/Tokyo",
            summary=CleaningMonthlySummary(
                completion_count=1,
                unique_task_count=1,
                participant_count=1,
                category_count=1,
            ),
            daily=[CleaningMonthlyDaily(day=now.date(), completion_count=1, unique_task_count=1)],
            categories=[],
            members=[],
            tasks=[],
        )


def test_list_cleaning_tasks_returns_group_tasks() -> None:
    summary = make_summary()

    response = list_cleaning_tasks(summary.group_id, TEST_USER, CleaningServiceStub(summary))

    assert response.items[0].id == summary.id


def test_create_cleaning_task_requires_group_admin() -> None:
    with pytest.raises(HTTPException) as error:
        create_cleaning_task(
            uuid4(),
            CleaningTaskCreate(name="お風呂", interval_days=1, category_id=uuid4()),
            TEST_USER,
            CleaningServiceStub(error=CleaningForbiddenError()),
        )

    assert error.value.status_code == 403


def test_complete_inactive_cleaning_task_returns_conflict() -> None:
    with pytest.raises(HTTPException) as error:
        complete_cleaning_task(uuid4(), TEST_USER, CleaningServiceStub(error=CleaningInactiveTaskError()))

    assert error.value.status_code == 409


def test_cleaning_categories_are_listed_for_group_members() -> None:
    category = make_category_summary()
    service = CleaningServiceStub()

    response = list_cleaning_categories(category.group_id, TEST_USER, service)

    assert response.items[0].name == "2階"


def test_create_cleaning_category_requires_csrf_and_returns_category() -> None:
    category = make_category_summary()

    response = create_cleaning_category(
        category.group_id,
        CleaningCategoryCreate(name="2階"),
        TEST_USER,
        CleaningServiceStub(),
    )

    assert response.name == "2階"


def test_update_cleaning_category_returns_category() -> None:
    response = update_cleaning_category(
        uuid4(),
        CleaningCategoryUpdate(name="1階"),
        TEST_USER,
        CleaningServiceStub(),
    )

    assert response.name == "2階"


def test_reorder_cleaning_categories_returns_ordered_categories() -> None:
    category_ids = [uuid4(), uuid4()]
    response = reorder_cleaning_categories(
        uuid4(),
        CleaningCategoryOrderUpdate(category_ids=category_ids),
        TEST_USER,
        CleaningServiceStub(),
    )

    assert len(response.items) == 2


def test_reorder_cleaning_categories_maps_invalid_order() -> None:
    with pytest.raises(HTTPException) as error:
        reorder_cleaning_categories(
            uuid4(),
            CleaningCategoryOrderUpdate(category_ids=[uuid4()]),
            TEST_USER,
            CleaningServiceStub(error=CleaningCategoryOrderInvalidError()),
        )

    assert error.value.status_code == 422


def test_delete_used_cleaning_category_returns_conflict() -> None:
    with pytest.raises(HTTPException) as error:
        delete_cleaning_category(
            uuid4(),
            TEST_USER,
            CleaningServiceStub(error=CleaningCategoryInUseError()),
        )

    assert error.value.status_code == 409


def test_monthly_report_returns_summary() -> None:
    response = get_cleaning_monthly_report(uuid4(), "2026-08", TEST_USER, CleaningServiceStub())

    assert response.month == "2026-08"
    assert response.summary.completion_count == 1


def test_monthly_report_maps_invalid_month_to_unprocessable_entity() -> None:
    with pytest.raises(HTTPException) as error:
        get_cleaning_monthly_report(
            uuid4(),
            "2026-08",
            TEST_USER,
            CleaningServiceStub(error=CleaningReportInvalidMonthError()),
        )

    assert error.value.status_code == 422


def test_cleaning_routes_are_registered_and_mutations_require_csrf() -> None:
    paths = create_app(Settings(app_env="test")).openapi()["paths"]

    assert {"get", "post"} <= set(paths["/api/v1/cleaning/groups/{group_id}/tasks"])
    assert {"get", "post"} <= set(paths["/api/v1/cleaning/groups/{group_id}/categories"])
    assert "get" in paths["/api/v1/cleaning/groups/{group_id}/reports/monthly"]
    assert {"get", "patch"} <= set(paths["/api/v1/cleaning/tasks/{task_id}"])
    assert {"patch", "delete"} <= set(paths["/api/v1/cleaning/categories/{category_id}"])
    assert "post" in paths["/api/v1/cleaning/tasks/{task_id}/completions"]

    from app.features.cleaning.router import router

    assert any(dependency.dependency is require_authenticated_user for dependency in router.dependencies)
    mutation_routes = [route for route in router.routes if route.methods & {"POST", "PATCH", "DELETE"}]
    assert mutation_routes
    assert all(
        any(dependency.dependency is require_csrf_token for dependency in route.dependencies)
        for route in mutation_routes
    )
