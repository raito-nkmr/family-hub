from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.features.chores.models import ChoreCategory, ChoreCompletion, ChoreTask


def make_chore_category(
    *,
    category_id: UUID | None = None,
    group_id: UUID | None = None,
    name: str = "浴室",
    sort_order: int = 0,
) -> ChoreCategory:
    now = datetime(2026, 7, 15, 3, tzinfo=UTC)
    return ChoreCategory(
        id=category_id or uuid4(),
        group_id=group_id or uuid4(),
        name=name,
        sort_order=sort_order,
        created_at=now,
        updated_at=now,
    )


def make_chore_task(
    *,
    task_id: UUID | None = None,
    group_id: UUID | None = None,
    created_by_user_id: UUID | None = None,
    name: str = "お風呂",
    category_id: UUID | None = None,
    interval_days: int = 1,
    is_active: bool = True,
) -> ChoreTask:
    now = datetime(2026, 7, 15, 3, tzinfo=UTC)
    return ChoreTask(
        id=task_id or uuid4(),
        group_id=group_id or uuid4(),
        name=name,
        category_id=category_id or uuid4(),
        interval_days=interval_days,
        is_active=is_active,
        created_by_user_id=created_by_user_id or uuid4(),
        created_at=now,
        updated_at=now,
    )


def make_completion(
    task_id: UUID,
    user_id: UUID,
    *,
    task_name: str = "お風呂",
    category_id: UUID | None = None,
    category_name: str = "浴室",
) -> ChoreCompletion:
    return ChoreCompletion(
        id=uuid4(),
        task_id=task_id,
        task_name_snapshot=task_name,
        category_id=category_id,
        category_name_snapshot=category_name,
        completed_by_user_id=user_id,
        completed_at=datetime(2026, 7, 15, 8, tzinfo=UTC),
    )
