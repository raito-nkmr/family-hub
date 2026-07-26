from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.features.auth.invitations import InvitationService


def get_invitation_service(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> InvitationService:
    return InvitationService(session, request.app.state.settings)
