from collections.abc import Collection
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.auth.models import User, UserSession
from app.features.auth.schemas import normalize_username
from app.features.auth.service import AuthContext, AuthService, InvalidCurrentPasswordError

__all__ = [
    "AuthContext",
    "AuthService",
    "InvalidCurrentPasswordError",
    "PublicUser",
    "User",
    "UserDirectory",
    "UserSession",
    "normalize_username",
]


@dataclass(frozen=True, slots=True)
class PublicUser:
    id: UUID
    username: str
    is_active: bool


class UserDirectory:
    """Minimal user information exposed to other features."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_by_ids(self, user_ids: Collection[UUID]) -> dict[UUID, PublicUser]:
        if not user_ids:
            return {}
        statement = select(User.id, User.username, User.is_active).where(User.id.in_(user_ids))
        return {
            user_id: PublicUser(id=user_id, username=username, is_active=is_active)
            for user_id, username, is_active in self._session.execute(statement).all()
        }

    def list_active(self) -> list[PublicUser]:
        statement = (
            select(User.id, User.username, User.is_active)
            .where(User.is_active.is_(True))
            .order_by(User.username.asc(), User.id.asc())
        )
        return [
            PublicUser(id=user_id, username=username, is_active=is_active)
            for user_id, username, is_active in self._session.execute(statement).all()
        ]
