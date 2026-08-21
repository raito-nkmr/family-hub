from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from app.features.notifications.models import NotificationType
from app.features.notifications.public import enqueue_group_notification


def test_enqueue_group_notification_locks_groups_before_reading_members() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    session.scalars.return_value.all.return_value = [group_id]
    session.execute.return_value.scalars.return_value.all.return_value = []

    enqueue_group_notification(
        session,
        {group_id},
        NotificationType.CHORE_DUE,
        "chore:task:due",
        {"url": "/chores"},
    )

    lock_statement = session.scalars.call_args.args[0]
    assert "ORDER BY family_groups.id FOR UPDATE" in str(lock_statement)
