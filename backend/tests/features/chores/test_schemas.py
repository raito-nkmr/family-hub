import pytest
from pydantic import ValidationError

from app.features.chores.schemas import (
    ChoreCategoryCreate,
    ChoreCategoryOrderUpdate,
    ChoreTaskCreate,
    ChoreTaskUpdate,
)


def test_chore_task_create_normalizes_name() -> None:
    category_id = "8d2f5c7a-8d25-4fa7-9c3c-17fdd7fd7a1e"
    body = ChoreTaskCreate(name="  お風呂  ", interval_days=1, category_id=category_id)

    assert body.name == "お風呂"
    assert str(body.category_id) == category_id


def test_chore_category_create_normalizes_name() -> None:
    body = ChoreCategoryCreate(name="  2階  ")

    assert body.name == "2階"


def test_chore_category_create_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        ChoreCategoryCreate(name="   ")


def test_chore_category_order_accepts_category_ids() -> None:
    category_id = "8d2f5c7a-8d25-4fa7-9c3c-17fdd7fd7a1e"

    assert str(ChoreCategoryOrderUpdate(category_ids=[category_id]).category_ids[0]) == category_id


@pytest.mark.parametrize("name", ["a" * 41])
def test_chore_category_create_rejects_long_name(name: str) -> None:
    with pytest.raises(ValidationError):
        ChoreCategoryCreate(name=name)


def test_chore_task_update_accepts_category_only() -> None:
    category_id = "8d2f5c7a-8d25-4fa7-9c3c-17fdd7fd7a1e"
    body = ChoreTaskUpdate(category_id=category_id)

    assert str(body.category_id) == category_id


@pytest.mark.parametrize("interval_days", [0, 3651])
def test_chore_task_create_rejects_invalid_interval(interval_days: int) -> None:
    with pytest.raises(ValidationError):
        ChoreTaskCreate(
            name="お風呂",
            interval_days=interval_days,
            category_id="8d2f5c7a-8d25-4fa7-9c3c-17fdd7fd7a1e",
        )


def test_chore_task_update_requires_a_change() -> None:
    with pytest.raises(ValidationError):
        ChoreTaskUpdate()
