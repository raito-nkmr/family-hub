from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.features.auth.admin_service import AdministrativeService


def get_administrative_service(session: Annotated[Session, Depends(get_session)]) -> AdministrativeService:
    return AdministrativeService(session)
