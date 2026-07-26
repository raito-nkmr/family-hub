from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.features.auth.public import UserDirectory
from app.features.groups.service import GroupService


def get_group_service(session: Annotated[Session, Depends(get_session)]) -> GroupService:
    return GroupService(session, UserDirectory(session))
