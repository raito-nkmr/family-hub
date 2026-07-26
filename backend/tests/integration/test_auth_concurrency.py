import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.features.auth.models import SystemRole, User, UserSession
from app.features.auth.passwords import hash_password
from app.features.auth.service import AuthService, InvalidCredentialsError

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(TEST_DATABASE_URL is None, reason="TEST_DATABASE_URL is not configured"),
]


def test_password_change_serializes_with_login() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL, connect_args={"options": "-c timezone=UTC"})
    user_id = uuid4()
    username = f"concurrency-{user_id.hex}"
    old_password = "old-password"
    new_password = "new-password"
    settings = Settings(app_env="test", database_url=TEST_DATABASE_URL)
    lock_acquired = Event()
    release_change = Event()
    login_started = Event()

    with Session(engine) as session:
        session.add(
            User(
                id=user_id,
                username=username,
                password_hash=hash_password(old_password),
                is_active=True,
                system_role=SystemRole.USER,
                created_at=datetime.now(UTC),
                password_changed_at=datetime.now(UTC),
            )
        )
        session.commit()

    def change_password_while_holding_lock() -> None:
        with Session(engine) as session:
            user = session.scalar(select(User).where(User.id == user_id).with_for_update())
            assert user is not None
            lock_acquired.set()
            assert release_change.wait(timeout=5)
            user.password_hash = hash_password(new_password)
            user.password_changed_at = datetime.now(UTC)
            session.commit()

    def attempt_old_password_login() -> None:
        assert lock_acquired.wait(timeout=5)
        login_started.set()
        with Session(engine) as session, pytest.raises(InvalidCredentialsError):
            AuthService(session, settings).login(username, old_password)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            change_future = executor.submit(change_password_while_holding_lock)
            login_future = executor.submit(attempt_old_password_login)
            assert login_started.wait(timeout=5)
            release_change.set()
            change_future.result(timeout=5)
            login_future.result(timeout=5)

        with Session(engine) as session:
            active_session_count = session.scalar(
                select(func.count()).select_from(UserSession).where(UserSession.user_id == user_id)
            )
            assert active_session_count == 0
    finally:
        release_change.set()
        with Session(engine) as session:
            session.execute(delete(User).where(User.id == user_id))
            session.commit()
        engine.dispose()
