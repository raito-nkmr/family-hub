import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.features.auth.admin_service import AdministrativeService
from app.features.auth.models import SystemRole, User, UserSession
from app.features.auth.passwords import hash_password

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(TEST_DATABASE_URL is None, reason="TEST_DATABASE_URL is not configured"),
]


def make_session(
    user_id,
    *,
    created_at: datetime,
    last_seen_at: datetime,
    expires_at: datetime,
    revoked_at: datetime | None = None,
) -> UserSession:
    token = uuid4().hex * 2
    return UserSession(
        id=uuid4(),
        user_id=user_id,
        token_hash=token,
        csrf_token="a" * 43,
        created_at=created_at,
        last_seen_at=last_seen_at,
        expires_at=expires_at,
        revoked_at=revoked_at,
    )


def test_list_users_counts_only_currently_authenticatable_sessions() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL, connect_args={"options": "-c timezone=UTC"})
    settings = Settings(app_env="test", database_url=TEST_DATABASE_URL)
    now = datetime.now(UTC)
    password_changed_at = now - timedelta(days=1)
    active_user_id = uuid4()
    inactive_user_id = uuid4()
    active_user = User(
        id=active_user_id,
        username=f"session-count-active-{active_user_id.hex}",
        password_hash=hash_password("unused-password"),
        is_active=True,
        system_role=SystemRole.USER,
        created_at=now,
        password_changed_at=password_changed_at,
    )
    inactive_user = User(
        id=inactive_user_id,
        username=f"session-count-inactive-{inactive_user_id.hex}",
        password_hash=hash_password("unused-password"),
        is_active=False,
        system_role=SystemRole.USER,
        created_at=now,
        password_changed_at=password_changed_at,
    )
    valid_session = make_session(
        active_user_id,
        created_at=now - timedelta(hours=1),
        last_seen_at=now - timedelta(hours=1),
        expires_at=now + timedelta(days=1),
    )
    idle_session = make_session(
        active_user_id,
        created_at=now - timedelta(days=2),
        last_seen_at=now - timedelta(seconds=settings.auth_session_idle_seconds + 1),
        expires_at=now + timedelta(days=1),
    )
    expired_session = make_session(
        active_user_id,
        created_at=now - timedelta(hours=1),
        last_seen_at=now - timedelta(hours=1),
        expires_at=now - timedelta(seconds=1),
    )
    revoked_session = make_session(
        active_user_id,
        created_at=now - timedelta(hours=1),
        last_seen_at=now - timedelta(hours=1),
        expires_at=now + timedelta(days=1),
        revoked_at=now,
    )
    password_old_session = make_session(
        active_user_id,
        created_at=password_changed_at - timedelta(seconds=1),
        last_seen_at=now - timedelta(hours=1),
        expires_at=now + timedelta(days=1),
    )
    inactive_user_session = make_session(
        inactive_user_id,
        created_at=now - timedelta(hours=1),
        last_seen_at=now - timedelta(hours=1),
        expires_at=now + timedelta(days=1),
    )

    with Session(engine) as session:
        session.add_all(
            [
                active_user,
                inactive_user,
                valid_session,
                idle_session,
                expired_session,
                revoked_session,
                password_old_session,
                inactive_user_session,
            ]
        )
        session.commit()

    try:
        with Session(engine) as session:
            users = AdministrativeService(session, settings).list_users()

        counts = {user.id: user.active_session_count for user in users}
        assert counts[active_user_id] == 1
        assert counts[inactive_user_id] == 0
    finally:
        with Session(engine) as session:
            session.execute(delete(User).where(User.id.in_((active_user_id, inactive_user_id))))
            session.commit()
        engine.dispose()
