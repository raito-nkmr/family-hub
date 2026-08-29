import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from app.features.auth.models import LoginRateLimit
from app.features.auth.rate_limit import LoginRateLimiter

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@pytest.mark.integration
@pytest.mark.skipif(TEST_DATABASE_URL is None, reason="TEST_DATABASE_URL is not configured")
def test_login_rate_limit_is_shared_and_resets_in_postgresql() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL, connect_args={"options": "-c timezone=UTC"})
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    limiter = LoginRateLimiter(maximum_attempts=1, window_seconds=60)
    key = f"127.0.0.1:integration-{uuid4()}"
    key_hash = limiter._hash_key(key)
    expired_hash = ""
    cleanup_hash = ""

    try:
        with session_factory() as session:
            session.execute(delete(LoginRateLimit).where(LoginRateLimit.key_hash == key_hash))
            session.commit()

        def acquire() -> int | None:
            with session_factory() as session:
                return limiter.try_acquire(session, key)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: acquire(), range(2)))

        assert sorted(result is None for result in results) == [False, True]

        with session_factory() as session:
            row = session.scalar(select(LoginRateLimit).where(LoginRateLimit.key_hash == key_hash))
            assert row is not None
            assert row.attempt_count == 1
            assert key not in row.key_hash
            limiter.reset(session, key)

        with session_factory() as session:
            assert session.scalar(select(LoginRateLimit).where(LoginRateLimit.key_hash == key_hash)) is None
            expired_key = f"127.0.0.1:expired-{uuid4()}"
            expired_hash = limiter._hash_key(expired_key)
            session.add(
                LoginRateLimit(
                    key_hash=expired_hash,
                    window_started_at=datetime.now(UTC) - timedelta(minutes=5),
                    attempt_count=1,
                    updated_at=datetime.now(UTC) - timedelta(minutes=5),
                )
            )
            session.commit()

        with session_factory() as session:
            cleanup_key = f"127.0.0.1:cleanup-{uuid4()}"
            cleanup_hash = limiter._hash_key(cleanup_key)
            assert limiter.try_acquire(session, cleanup_key) is None
            assert session.scalar(select(LoginRateLimit).where(LoginRateLimit.key_hash == expired_hash)) is None
    finally:
        with session_factory() as session:
            session.execute(
                delete(LoginRateLimit).where(LoginRateLimit.key_hash.in_([key_hash, expired_hash, cleanup_hash]))
            )
            session.commit()
        engine.dispose()
