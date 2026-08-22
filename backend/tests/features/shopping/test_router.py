from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.features.auth.dependencies import AuthenticatedUser, require_authenticated_user, require_csrf_token
from app.features.shopping.router import (
    _category_response,
    _list_item_response,
    create_shopping_item,
    purchase_shopping_item,
)
from app.features.shopping.schemas import ShoppingItemCreate
from app.features.shopping.service import ShoppingItemSummary, ShoppingNotFoundError, ShoppingStateConflictError
from app.features.shopping.workflow import ShoppingCategorySummary, ShoppingListItemSummary
from app.main import create_app

TEST_USER = AuthenticatedUser(id=uuid4(), username="owner")


def make_summary() -> ShoppingItemSummary:
    now = datetime(2026, 7, 15, 3, tzinfo=UTC)
    return ShoppingItemSummary(
        id=uuid4(),
        group_id=uuid4(),
        name="牛乳",
        created_by_user_id=TEST_USER.id,
        created_at=now,
        updated_at=now,
        purchased_by_user_id=None,
        purchased_by_username=None,
        purchased_at=None,
    )


class ShoppingServiceStub:
    def __init__(self, summary: ShoppingItemSummary | None = None, error: Exception | None = None) -> None:
        self.summary = summary
        self.error = error

    def create_item(self, group_id: UUID, user_id: UUID, name: str) -> ShoppingItemSummary:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        assert name == "牛乳"
        assert self.summary is not None
        return self.summary

    def purchase_item(self, item_id: UUID, user_id: UUID) -> ShoppingItemSummary:
        if self.error:
            raise self.error
        assert user_id == TEST_USER.id
        assert self.summary is not None
        return self.summary


def test_create_shopping_item_returns_item() -> None:
    summary = make_summary()

    response = create_shopping_item(
        summary.group_id,
        ShoppingItemCreate(name="牛乳"),
        TEST_USER,
        ShoppingServiceStub(summary),
    )

    assert response.id == summary.id


def test_workflow_summary_responses_accept_dataclass_objects() -> None:
    now = datetime(2026, 7, 15, 3, tzinfo=UTC)
    category = ShoppingCategorySummary(
        id=uuid4(),
        group_id=uuid4(),
        name="食品",
        sort_order=0,
        created_at=now,
        updated_at=now,
    )
    item = ShoppingListItemSummary(
        id=uuid4(),
        group_id=category.group_id,
        name="牛乳",
        created_by_user_id=TEST_USER.id,
        created_at=now,
        updated_at=now,
        assignee_user_id=None,
        assignee_username=None,
        category_id=category.id,
        category_name=category.name,
    )

    assert _category_response(category).id == category.id
    assert _list_item_response(item).category_name == category.name


def test_purchase_changed_item_returns_conflict() -> None:
    with pytest.raises(HTTPException) as error:
        purchase_shopping_item(uuid4(), TEST_USER, ShoppingServiceStub(error=ShoppingStateConflictError()))

    assert error.value.status_code == 409


def test_non_member_receives_not_found() -> None:
    with pytest.raises(HTTPException) as error:
        create_shopping_item(
            uuid4(),
            ShoppingItemCreate(name="牛乳"),
            TEST_USER,
            ShoppingServiceStub(error=ShoppingNotFoundError()),
        )

    assert error.value.status_code == 404


def test_shopping_routes_are_registered_and_mutations_require_csrf() -> None:
    paths = create_app(Settings(app_env="test")).openapi()["paths"]

    assert {"get", "post"} <= set(paths["/api/v1/shopping/groups/{group_id}/items"])
    assert {"post", "delete"} <= set(paths["/api/v1/shopping/items/{item_id}/purchase"])
    assert {"get", "post"} <= set(paths["/api/v1/shopping/groups/{group_id}/requests"])
    assert {"get", "post"} <= set(paths["/api/v1/shopping/groups/{group_id}/trips"])
    assert "get" in paths["/api/v1/shopping/groups/{group_id}/statistics"]
    assert "post" in paths["/api/v1/shopping/requests/{item_id}/purchase"]
    assert "post" in paths["/api/v1/shopping/purchases/{purchase_id}/reverse"]

    from app.features.shopping.router import router

    assert any(dependency.dependency is require_authenticated_user for dependency in router.dependencies)
    mutation_routes = [route for route in router.routes if route.methods & {"POST", "PATCH", "DELETE"}]
    assert mutation_routes
    assert all(
        any(dependency.dependency is require_csrf_token for dependency in route.dependencies)
        for route in mutation_routes
    )
