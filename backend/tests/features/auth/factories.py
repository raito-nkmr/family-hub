from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.features.auth.models import SystemRole, User, UserSession


def make_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        username="owner",
        password_hash="password-hash",
        is_active=True,
        system_role=SystemRole.USER,
        created_at=now - timedelta(days=2),
        password_changed_at=now - timedelta(days=2),
    )


def make_user_session(user: User | None = None) -> UserSession:
    now = datetime.now(UTC)
    session_user = user or make_user()
    return UserSession(
        id=uuid4(),
        user_id=session_user.id,
        token_hash="a" * 64,
        csrf_token="c" * 43,
        created_at=now - timedelta(hours=1),
        last_seen_at=now,
        expires_at=now + timedelta(days=1),
        revoked_at=None,
        user=session_user,
    )
