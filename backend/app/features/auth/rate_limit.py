import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.features.auth.models import LoginRateLimit


class LoginRateLimiter:
    def __init__(self, maximum_attempts: int, window_seconds: int) -> None:
        self._maximum_attempts = maximum_attempts
        self._window = timedelta(seconds=window_seconds)

    def try_acquire(self, session: Session, key: str) -> int | None:
        """Atomically reserve one login attempt across all application processes."""
        now = datetime.now(UTC)
        key_hash = self._hash_key(key)
        try:
            session.execute(delete(LoginRateLimit).where(LoginRateLimit.updated_at < now - self._window))
            session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key_hash, 0))))
            row = session.scalar(select(LoginRateLimit).where(LoginRateLimit.key_hash == key_hash).with_for_update())
            if row is None:
                session.add(
                    LoginRateLimit(
                        key_hash=key_hash,
                        window_started_at=now,
                        attempt_count=1,
                        updated_at=now,
                    )
                )
                session.commit()
                return None

            if now - row.window_started_at >= self._window:
                row.window_started_at = now
                row.attempt_count = 1
                row.updated_at = now
                session.commit()
                return None

            if row.attempt_count >= self._maximum_attempts:
                retry_after = max(1, int((self._window - (now - row.window_started_at)).total_seconds()) + 1)
                session.commit()
                return retry_after

            row.attempt_count += 1
            row.updated_at = now
            session.commit()
            return None
        except SQLAlchemyError:
            session.rollback()
            raise

    def reset(self, session: Session, key: str) -> None:
        key_hash = self._hash_key(key)
        try:
            session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key_hash, 0))))
            session.execute(delete(LoginRateLimit).where(LoginRateLimit.key_hash == key_hash))
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            raise

    @staticmethod
    def _hash_key(key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()
