"""In-process key/value store with TTLs: a drop-in for the few Redis calls this app uses.

Used when REDIS_URL is "memory://" (the default), so local development and demos need no Redis and no Docker.
Limits to know about: data lives in this process only (lost on restart, not shared between workers), so run a
single worker with it. Production with several workers should set REDIS_URL to a real Redis.
"""
import time
from collections.abc import Callable

_PRUNE_EVERY = 256  # sweep expired keys every N writes so abandoned sessions cannot pile up


class MemoryStore:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._data: dict[str, tuple[str, float | None]] = {}  # key -> (value, expires_at)
        self._writes = 0

    def _alive(self, key: str) -> tuple[str, float | None] | None:
        item = self._data.get(key)
        if item is None:
            return None
        if item[1] is not None and item[1] <= self._clock():
            del self._data[key]
            return None
        return item

    def _prune(self) -> None:
        self._writes += 1
        if self._writes % _PRUNE_EVERY == 0:
            now = self._clock()
            for key in [k for k, (_, exp) in self._data.items() if exp is not None and exp <= now]:
                del self._data[key]

    async def ping(self) -> bool:
        return True

    async def get(self, key: str) -> str | None:
        item = self._alive(key)
        return None if item is None else item[0]

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._data[key] = (value, None if ex is None else self._clock() + ex)
        self._prune()
        return True

    async def expire(self, key: str, seconds: int) -> bool:
        item = self._alive(key)
        if item is None:
            return False
        self._data[key] = (item[0], self._clock() + seconds)
        return True

    async def ttl(self, key: str) -> int:
        """Seconds left; -1 if the key has no expiry, -2 if it does not exist (same as Redis)."""
        item = self._alive(key)
        if item is None:
            return -2
        if item[1] is None:
            return -1
        return max(0, round(item[1] - self._clock()))

    async def delete(self, *keys: str) -> int:
        return sum(1 for k in keys if self._alive(k) is not None and self._data.pop(k, None) is not None)

    async def incr(self, key: str) -> int:
        """Atomic in a single event loop. Keeps any existing expiry (used by rate limits later)."""
        item = self._alive(key)
        value = int(item[0]) + 1 if item else 1
        self._data[key] = (str(value), item[1] if item else None)
        return value

    async def aclose(self) -> None:
        self._data.clear()
