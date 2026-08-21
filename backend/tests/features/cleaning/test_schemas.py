import pytest
from pydantic import ValidationError

from app.features.cleaning.models import CleaningTaskCategory
from app.features.cleaning.schemas import CleaningTaskCreate, CleaningTaskUpdate


def test_cleaning_task_create_normalizes_name() -> None:
    body = CleaningTaskCreate(name="  お風呂  ", interval_days=1)

    assert body.name == "お風呂"
    assert body.category is CleaningTaskCategory.CLEANING


def test_cleaning_task_create_accepts_category() -> None:
    body = CleaningTaskCreate(name="花に水", interval_days=2, category=CleaningTaskCategory.WATERING)

    assert body.category is CleaningTaskCategory.WATERING


def test_cleaning_task_update_accepts_category_only() -> None:
    body = CleaningTaskUpdate(category=CleaningTaskCategory.CHILDREN)

    assert body.category is CleaningTaskCategory.CHILDREN


@pytest.mark.parametrize("interval_days", [0, 3651])
def test_cleaning_task_create_rejects_invalid_interval(interval_days: int) -> None:
    with pytest.raises(ValidationError):
        CleaningTaskCreate(name="お風呂", interval_days=interval_days)


def test_cleaning_task_update_requires_a_change() -> None:
    with pytest.raises(ValidationError):
        CleaningTaskUpdate()
