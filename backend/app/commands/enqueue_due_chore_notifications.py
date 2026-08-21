from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_management_settings
from app.database.session import create_database_engine
from app.features.chores.models import ChoreCompletion, ChoreTask
from app.features.notifications.models import NotificationType
from app.features.notifications.public import enqueue_group_notification


def enqueue_due_chore_notifications(session: Session) -> int:
    latest_completion = (
        select(
            ChoreCompletion.task_id,
            func.max(ChoreCompletion.completed_at).label("completed_at"),
        )
        .group_by(ChoreCompletion.task_id)
        .subquery()
    )
    rows = session.execute(
        select(ChoreTask, latest_completion.c.completed_at)
        .outerjoin(latest_completion, latest_completion.c.task_id == ChoreTask.id)
        .where(ChoreTask.is_active.is_(True))
        .order_by(ChoreTask.id)
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
            NotificationType.CHORE_DUE,
            f"chores: {task.id}:{due_at.isoformat()}",
            {"url": "/chores", "task_id": str(task.id)},
        )
    session.commit()
    return enqueued


def main() -> None:
    settings = get_management_settings()
    engine = create_database_engine(settings)
    try:
        with Session(engine) as session:
            enqueued = enqueue_due_chore_notifications(session)
    finally:
        engine.dispose()
    print(f"Enqueued chore notifications for {enqueued} recipient(s)")


if __name__ == "__main__":
    main()
