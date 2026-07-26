from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_management_settings
from app.database.session import create_database_engine
from app.features.cleaning.models import CleaningCompletion, CleaningTask
from app.features.notifications.models import NotificationType
from app.features.notifications.public import enqueue_group_notification


def enqueue_due_cleaning_notifications(session: Session) -> int:
    latest_completion = (
        select(
            CleaningCompletion.task_id,
            func.max(CleaningCompletion.completed_at).label("completed_at"),
        )
        .group_by(CleaningCompletion.task_id)
        .subquery()
    )
    rows = session.execute(
        select(CleaningTask, latest_completion.c.completed_at)
        .outerjoin(latest_completion, latest_completion.c.task_id == CleaningTask.id)
        .where(CleaningTask.is_active.is_(True))
        .order_by(CleaningTask.id)
    ).all()
    now = datetime.now(UTC)
    enqueued = 0
    for task, completed_at in rows:
        due_at = (completed_at or task.created_at) + timedelta(days=task.interval_days)
        if due_at > now:
            continue
        enqueued += enqueue_group_notification(
            session,
            {task.group_id},
            NotificationType.CLEANING_DUE,
            f"cleaning:{task.id}:{due_at.isoformat()}",
            {"url": "/cleaning", "task_id": str(task.id)},
        )
    session.commit()
    return enqueued


def main() -> None:
    settings = get_management_settings()
    engine = create_database_engine(settings)
    try:
        with Session(engine) as session:
            enqueued = enqueue_due_cleaning_notifications(session)
    finally:
        engine.dispose()
    print(f"Enqueued cleaning notifications for {enqueued} recipient(s)")


if __name__ == "__main__":
    main()
