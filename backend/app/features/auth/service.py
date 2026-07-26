import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings
from app.features.auth.models import User, UserSession
from app.features.auth.passwords import hash_password, verify_dummy_password, verify_password


class InvalidCredentialsError(Exception):
    pass


class InvalidCurrentPasswordError(Exception):
    pass


class UserSessionNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CreatedSession:
    user: User
    token: str
    csrf_token: str


@dataclass(frozen=True, slots=True)
class AuthContext:
    user: User
    user_session: UserSession


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def login(self, username: str, password: str) -> CreatedSession:
        user = self._session.scalar(
            select(User).where(User.username == username).with_for_update().execution_options(populate_existing=True)
        )
        if user is None:
            verify_dummy_password(password)
            raise InvalidCredentialsError
        password_matches = verify_password(password, user.password_hash)
        if not password_matches or not user.is_active:
            raise InvalidCredentialsError

        now = datetime.now(UTC)
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        user_session = UserSession(
            id=uuid4(),
            user_id=user.id,
            token_hash=hash_session_token(token),
            csrf_token=csrf_token,
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(seconds=self._settings.auth_session_absolute_seconds),
            revoked_at=None,
        )
        self._session.add(user_session)
        self._session.commit()
        return CreatedSession(user=user, token=token, csrf_token=csrf_token)

    def authenticate(self, token: str) -> AuthContext | None:
        statement = (
            select(UserSession)
            .options(joinedload(UserSession.user))
            .where(UserSession.token_hash == hash_session_token(token))
        )
        user_session = self._session.scalar(statement)
        if user_session is None:
            return None

        now = datetime.now(UTC)
        idle_deadline = user_session.last_seen_at + timedelta(seconds=self._settings.auth_session_idle_seconds)
        if (
            user_session.revoked_at is not None
            or not user_session.user.is_active
            or user_session.expires_at <= now
            or idle_deadline <= now
            or user_session.created_at < user_session.user.password_changed_at
        ):
            return None

        if user_session.last_seen_at + timedelta(seconds=self._settings.auth_session_touch_seconds) <= now:
            user_session.last_seen_at = now
            self._session.commit()
        return AuthContext(user=user_session.user, user_session=user_session)

    def logout(self, context: AuthContext) -> None:
        context.user_session.revoked_at = datetime.now(UTC)
        self._session.commit()

    def logout_all(self, user_id: UUID) -> None:
        statement = (
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        self._session.execute(statement)
        self._session.commit()

    def verify_current_password(self, user_id: UUID, password: str) -> None:
        user = self._session.get(User, user_id)
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            raise InvalidCurrentPasswordError

    def list_sessions(self, context: AuthContext) -> list[UserSession]:
        now = datetime.now(UTC)
        idle_deadline = now - timedelta(seconds=self._settings.auth_session_idle_seconds)
        statement = (
            select(UserSession)
            .where(
                UserSession.user_id == context.user.id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
                UserSession.last_seen_at > idle_deadline,
                UserSession.created_at >= context.user.password_changed_at,
            )
            .order_by(UserSession.last_seen_at.desc(), UserSession.id)
        )
        return list(self._session.scalars(statement).all())

    def revoke_session(self, context: AuthContext, session_id: UUID) -> bool:
        user_session = self._session.scalar(
            select(UserSession).where(
                UserSession.id == session_id,
                UserSession.user_id == context.user.id,
                UserSession.revoked_at.is_(None),
            )
        )
        if user_session is None:
            raise UserSessionNotFoundError
        user_session.revoked_at = datetime.now(UTC)
        self._session.commit()
        return user_session.id == context.user_session.id

    def change_password(self, context: AuthContext, current_password: str, new_password: str) -> None:
        user = self._session.scalar(
            select(User).where(User.id == context.user.id).with_for_update().execution_options(populate_existing=True)
        )
        if user is None or not user.is_active or not verify_password(current_password, user.password_hash):
            raise InvalidCurrentPasswordError

        changed_at = datetime.now(UTC)
        user.password_hash = hash_password(new_password)
        user.password_changed_at = changed_at
        statement = (
            update(UserSession)
            .where(UserSession.user_id == context.user.id, UserSession.revoked_at.is_(None))
            .values(revoked_at=changed_at)
        )
        self._session.execute(statement)
        self._session.commit()
