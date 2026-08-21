import pytest
from pydantic import ValidationError

from app.features.cleaning.schemas import (
    CleaningCategoryCreate,
    CleaningCategoryOrderUpdate,
    CleaningTaskCreate,
    CleaningTaskUpdate,
)


def test_cleaning_task_create_normalizes_name() -> None:
    category_id = "8d2f5c7a-8d25-4fa7-9c3c-17fdd7fd7a1e"
    body = CleaningTaskCreate(name="  お風呂  ", interval_days=1, category_id=category_id)

    assert body.name == "お風呂"
    assert str(body.category_id) == category_id


def test_cleaning_category_create_normalizes_name() -> None:
    body = CleaningCategoryCreate(name="  2階  ")

    assert body.name == "2階"


def test_cleaning_category_create_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        CleaningCategoryCreate(name="   ")


def test_cleaning_category_order_accepts_category_ids() -> None:
    category_id = "8d2f5c7a-8d25-4fa7-9c3c-17fdd7fd7a1e"

    assert str(CleaningCategoryOrderUpdate(category_ids=[category_id]).category_ids[0]) == category_id


@pytest.mark.parametrize("name", ["a" * 41])
def test_cleaning_category_create_rejects_long_name(name: str) -> None:
    with pytest.raises(ValidationError):
        CleaningCategoryCreate(name=name)


def test_cleaning_task_update_accepts_category_only() -> None:
    category_id = "8d2f5c7a-8d25-4fa7-9c3c-17fdd7fd7a1e"
    body = CleaningTaskUpdate(category_id=category_id)

    assert str(body.category_id) == category_id


@pytest.mark.parametrize("interval_days", [0, 3651])
def test_cleaning_task_create_rejects_invalid_interval(interval_days: int) -> None:
    with pytest.raises(ValidationError):
        CleaningTaskCreate(
            name="お風呂",
            interval_days=interval_days,
            category_id="8d2f5c7a-8d25-4fa7-9c3c-17fdd7fd7a1e",
        )


def test_cleaning_task_update_requires_a_change() -> None:
    with pytest.raises(ValidationError):
        CleaningTaskUpdate()
