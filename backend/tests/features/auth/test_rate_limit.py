from datetime import UTC, datetime
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from app.features.auth.models import LoginRateLimit
from app.features.auth.rate_limit import LoginRateLimiter


def test_login_rate_limiter_blocks_after_maximum_failures_and_can_reset() -> None:
    session = MagicMock(spec=Session)
    limiter = LoginRateLimiter(maximum_attempts=2, window_seconds=60)
    row = LoginRateLimit(
        key_hash=limiter._hash_key("client:owner"),
        window_started_at=datetime.now(UTC),
        attempt_count=1,
        updated_at=datetime.now(UTC),
    )

    session.scalar.return_value = None
    assert limiter.try_acquire(session, "client:first") is None

    session.scalar.return_value = row
    assert limiter.try_acquire(session, "client:owner") is None
    assert row.attempt_count == 2
    assert limiter.try_acquire(session, "client:owner") is not None

    limiter.reset(session, "client:owner")
    session.commit.assert_called()
    assert limiter._hash_key("client:owner") != "client:owner"
