from collections import OrderedDict, deque
from threading import Lock
from time import monotonic


class LoginRateLimiter:
    def __init__(self, maximum_attempts: int, window_seconds: int, maximum_keys: int = 10_000) -> None:
        self._maximum_attempts = maximum_attempts
        self._window_seconds = window_seconds
        self._maximum_keys = maximum_keys
        self._attempts: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def retry_after(self, key: str) -> int | None:
        now = monotonic()
        with self._lock:
            attempts = self._active_attempts(key, now)
            if len(attempts) < self._maximum_attempts:
                return None
            return max(1, int(self._window_seconds - (now - attempts[0])) + 1)

    def record_failure(self, key: str) -> None:
        now = monotonic()
        with self._lock:
            attempts = self._active_attempts(key, now, create=True)
            attempts.append(now)
            self._attempts.move_to_end(key)
            while len(self._attempts) > self._maximum_keys:
                self._attempts.popitem(last=False)

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def _active_attempts(self, key: str, now: float, *, create: bool = False) -> deque[float]:
        attempts = self._attempts.get(key)
        if attempts is None:
            if not create:
                return deque()
            attempts = deque()
            self._attempts[key] = attempts
        cutoff = now - self._window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        if not attempts and not create:
            self._attempts.pop(key, None)
        return attempts
