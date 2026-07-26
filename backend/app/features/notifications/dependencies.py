from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.features.notifications.service import NotificationService


def get_notification_service(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> NotificationService:
    return NotificationService(session, request.app.state.settings)
