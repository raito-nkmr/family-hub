from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.features.audit.models import AdministrativeAuditEvent

__all__ = ["AdministrativeAuditEvent", "record_administrative_event"]


def record_administrative_event(
    session: Session,
    *,
    scope: str,
    action: str,
    actor_user_id: UUID | None,
    actor_username: str,
    target_type: str,
    target_id: str,
    group_id: UUID | None = None,
    details: dict[str, object] | None = None,
) -> AdministrativeAuditEvent:
    event = AdministrativeAuditEvent(
        id=uuid4(),
        scope=scope,
        action=action,
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        group_id=group_id,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
    )
    session.add(event)
    return event
