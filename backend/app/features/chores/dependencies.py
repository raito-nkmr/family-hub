from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.features.auth.public import UserDirectory
from app.features.chores.reporting import ChoreMonthlyReportService
from app.features.chores.service import ChoreService


def get_chore_service(session: Annotated[Session, Depends(get_session)]) -> ChoreService:
    return ChoreService(session, UserDirectory(session))


def get_chore_monthly_report_service(session: Annotated[Session, Depends(get_session)]) -> ChoreMonthlyReportService:
    return ChoreMonthlyReportService(session)
