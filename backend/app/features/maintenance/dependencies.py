from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.features.maintenance.service import MaintenanceService
from app.features.photos.public import PhotoStorage


def get_maintenance_service(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> MaintenanceService:
    return MaintenanceService(session, PhotoStorage(request.app.state.settings))
