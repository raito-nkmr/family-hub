from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.features.auth.admin_service import AdministrativeService


def get_administrative_service(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> AdministrativeService:
    return AdministrativeService(session, request.app.state.settings)
