from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.features.auth.public import UserDirectory
from app.features.cleaning.reporting import CleaningReportService
from app.features.cleaning.service import CleaningService


def get_cleaning_service(session: Annotated[Session, Depends(get_session)]) -> CleaningService:
    return CleaningService(session, UserDirectory(session))


def get_cleaning_report_service(session: Annotated[Session, Depends(get_session)]) -> CleaningReportService:
    return CleaningReportService(session)
