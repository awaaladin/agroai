"""Abuse protection: per-device and per-IP rate limits, plus a global daily AI-call cap.

Works on any store with `incr`, `expire` and `ttl` (the built-in MemoryStore or Redis). Fixed windows: the first hit
starts the window, the counter's TTL is the window, and the key vanishes by itself. Keys use a hash of the IP so raw
addresses are never stored or logged.
"""
import hashlib
import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Request

from app.core.config import Settings
from app.core.security import current_device

log = logging.getLogger("agroai.limits")


class RateLimited(Exception):
    """Raised to produce a 429 with a Retry-After header and a friendly message in both languages."""

    def __init__(self, retry_after: int, message: str, message_pcm: str, scope: str):
        super().__init__(message)
        self.retry_after = max(1, int(retry_after))
        self.message = message
        self.message_pcm = message_pcm
        self.scope = scope


def too_fast(retry_after: int, scope: str) -> RateLimited:
    return RateLimited(
        retry_after,
        f"You are asking too fast. Please wait {max(1, retry_after)} seconds and try again.",
        f"You dey ask too fast. Abeg wait {max(1, retry_after)} seconds then try again.",
        scope,
    )


def client_ip(request: Request, trusted_hops: int) -> str:
    """The caller's IP. Behind `trusted_hops` proxies, take the entry the nearest trusted proxy added to X-Forwarded-For."""
    if trusted_hops > 0:
        parts = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if len(parts) >= trusted_hops:
            return parts[-trusted_hops]
    return request.client.host if request.client else "unknown"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


async def hit(store, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Count one request. Returns (allowed, seconds_until_the_window_resets)."""
    count = await store.incr(key)
    if count == 1:
        await store.expire(key, window_seconds)
    ttl = await store.ttl(key)
    if ttl < 0:  # a crash between incr and expire must never leave a counter that never resets
        await store.expire(key, window_seconds)
        ttl = window_seconds
    return count <= limit, ttl


class RateLimiter:
    """Named buckets from settings. Each bucket checks a per-device and a per-IP limit."""

    def __init__(self, store, settings: Settings):
        self.store = store
        self.trusted_hops = settings.trusted_proxy_hops
        # bucket -> (device limit, ip limit, window seconds)
        self.buckets = {
            "general": (settings.rate_device_per_minute, settings.rate_ip_per_minute, 60),
            "diagnose": (settings.rate_diagnose_device_per_hour, settings.rate_diagnose_ip_per_hour, 3600),
            "chat": (settings.rate_chat_device_per_hour, settings.rate_chat_ip_per_hour, 3600),
            "anon": (None, settings.rate_anon_ip_per_hour, 3600),  # tokens are free, so only the IP can be limited
        }

    async def check(self, bucket: str, request: Request, device_id: str | None) -> None:
        device_limit, ip_limit, window = self.buckets[bucket]
        ip = _digest(client_ip(request, self.trusted_hops))
        checks = [("ip", f"agroai:rl:{bucket}:ip:{ip}", ip_limit)]
        if device_id is not None and device_limit is not None:
            checks.append(("device", f"agroai:rl:{bucket}:dev:{_digest(device_id)}", device_limit))
        worst: tuple[str, int] | None = None
        for scope, key, limit in checks:
            allowed, ttl = await hit(self.store, key, limit, window)
            if not allowed and (worst is None or ttl > worst[1]):
                worst = (scope, ttl)
        if worst:
            log.warning("rate limit hit", extra={"extra_fields": {"bucket": bucket, "scope": worst[0], "retry_after": worst[1]}})
            raise too_fast(worst[1], f"{bucket}:{worst[0]}")


def limit(bucket: str) -> Callable:
    """Dependency factory for authenticated routes: 401 first, then the bucket's device and IP limits."""

    async def dependency(request: Request, device_id: str = Depends(current_device)) -> None:
        await request.app.state.limiter.check(bucket, request, device_id)

    return dependency


def limit_ip_only(bucket: str) -> Callable:
    async def dependency(request: Request) -> None:
        await request.app.state.limiter.check(bucket, request, None)

    return dependency


class SpendCap:
    """Global daily cap on paid AI calls (every model call counts, including retries), so a demo cannot run up a bill."""

    def __init__(self, store, daily_limit: int, now: Callable[[], datetime] | None = None):
        self.store = store
        self.daily_limit = daily_limit
        self._now = now or (lambda: datetime.now(timezone.utc))

    def _key_and_reset(self) -> tuple[str, int]:
        now = self._now()
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return f"agroai:ai_calls:{now:%Y-%m-%d}", int((midnight - now).total_seconds())

    async def reserve(self) -> None:
        """Count one AI call or raise RateLimited (429) when today's budget is used up."""
        key, seconds_left = self._key_and_reset()
        count = await self.store.incr(key)
        if count == 1:
            await self.store.expire(key, 48 * 3600)
        if count > self.daily_limit:
            log.warning("daily AI cap reached", extra={"extra_fields": {"limit": self.daily_limit}})
            raise RateLimited(
                seconds_left,
                "The advisor has answered as many farmers as it can for today. Please try again tomorrow, or ask your extension officer.",
                "The advisor don answer as many farmers as e fit today. Abeg try again tomorrow, or ask your extension officer.",
                "daily_ai_cap",
            )

    async def used_today(self) -> int:
        key, _ = self._key_and_reset()
        raw = await self.store.get(key)
        return int(raw) if raw else 0
