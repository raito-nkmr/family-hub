import pytest
from pydantic import ValidationError

from app.features.cleaning.schemas import CleaningTaskCreate, CleaningTaskUpdate


def test_cleaning_task_create_normalizes_name() -> None:
    body = CleaningTaskCreate(name="  お風呂  ", interval_days=1)

    assert body.name == "お風呂"


@pytest.mark.parametrize("interval_days", [0, 3651])
def test_cleaning_task_create_rejects_invalid_interval(interval_days: int) -> None:
    with pytest.raises(ValidationError):
        CleaningTaskCreate(name="お風呂", interval_days=interval_days)


def test_cleaning_task_update_requires_a_change() -> None:
    with pytest.raises(ValidationError):
        CleaningTaskUpdate()
