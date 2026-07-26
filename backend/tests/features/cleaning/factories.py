from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.features.cleaning.models import CleaningCompletion, CleaningTask


def make_cleaning_task(
    *,
    task_id: UUID | None = None,
    group_id: UUID | None = None,
    created_by_user_id: UUID | None = None,
    name: str = "お風呂",
    interval_days: int = 1,
    is_active: bool = True,
) -> CleaningTask:
    now = datetime(2026, 7, 15, 3, tzinfo=UTC)
    return CleaningTask(
        id=task_id or uuid4(),
        group_id=group_id or uuid4(),
        name=name,
        interval_days=interval_days,
        is_active=is_active,
        created_by_user_id=created_by_user_id or uuid4(),
        created_at=now,
        updated_at=now,
    )


def make_completion(task_id: UUID, user_id: UUID) -> CleaningCompletion:
    return CleaningCompletion(
        id=uuid4(),
        task_id=task_id,
        completed_by_user_id=user_id,
        completed_at=datetime(2026, 7, 15, 8, tzinfo=UTC),
    )
