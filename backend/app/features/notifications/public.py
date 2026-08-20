from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.features.groups.public import FamilyGroupMember, lock_group_ids
from app.features.notifications.models import NotificationOutbox, NotificationOutboxStatus, NotificationType

__all__ = ["NotificationType", "enqueue_group_notification"]


def enqueue_group_notification(
    session: Session,
    group_ids: set[UUID],
    notification_type: NotificationType,
    deduplication_key: str,
    payload: dict[str, object],
    *,
    exclude_user_id: UUID | None = None,
) -> int:
    if not group_ids:
        return 0
    lock_group_ids(session, group_ids)
    statement = select(FamilyGroupMember.user_id).where(FamilyGroupMember.group_id.in_(group_ids)).distinct()
    if exclude_user_id is not None:
        statement = statement.where(FamilyGroupMember.user_id != exclude_user_id)
    recipient_ids = list(session.execute(statement).scalars().all())
    now = datetime.now(UTC)
    for recipient_id in recipient_ids:
        session.execute(
            insert(NotificationOutbox)
            .values(
                id=uuid4(),
                recipient_user_id=recipient_id,
                notification_type=notification_type,
                deduplication_key=deduplication_key,
                payload=payload,
                status=NotificationOutboxStatus.PENDING,
                attempt_count=0,
                available_at=now,
                created_at=now,
                processed_at=None,
                last_error=None,
            )
            .on_conflict_do_nothing(
                constraint="uq_notification_outbox_recipient_dedupe",
            )
        )
    return len(recipient_ids)
