from app.features.auth.rate_limit import LoginRateLimiter


def test_login_rate_limiter_blocks_after_maximum_failures_and_can_reset() -> None:
    limiter = LoginRateLimiter(maximum_attempts=2, window_seconds=60)

    assert limiter.retry_after("client:owner") is None


def test_login_rate_limiter_bounds_tracked_identity_keys() -> None:
    limiter = LoginRateLimiter(maximum_attempts=2, window_seconds=60, maximum_keys=2)

    limiter.record_failure("client:first")
    limiter.record_failure("client:second")
    limiter.record_failure("client:third")

    assert list(limiter._attempts) == ["client:second", "client:third"]
    limiter.record_failure("client:owner")
    limiter.record_failure("client:owner")
    assert limiter.retry_after("client:owner") is not None

    limiter.reset("client:owner")

    assert limiter.retry_after("client:owner") is None
