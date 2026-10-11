"""Structured JSON logs with a request ID. Never log request bodies, images or locations."""
import json
import logging
import time
import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        payload.update(getattr(record, "extra_fields", {}))
        return json.dumps(payload)


def setup_logging() -> None:
    root = logging.getLogger()
    # Idempotent: drop only our own earlier handler, so repeated create_app() calls (and test log capture) still work.
    root.handlers[:] = [h for h in root.handlers if not isinstance(h.formatter, JsonFormatter)]
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    for noisy in ("httpx", "httpx2", "httpcore", "anthropic"):  # HTTP client chatter is not ours to log
        logging.getLogger(noisy).setLevel(logging.WARNING)


class RequestContextMiddleware:
    """Pure-ASGI middleware: assigns a request ID, echoes it as X-Request-ID, logs method/path/status/ms only."""

    def __init__(self, app):
        self.app = app
        self.log = logging.getLogger("agroai.access")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        rid = uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        start = time.perf_counter()
        status = 500

        async def send_wrapper(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", rid.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            ms = round((time.perf_counter() - start) * 1000)
            self.log.info(
                "request",
                extra={"extra_fields": {"method": scope["method"], "path": scope["path"], "status": status, "ms": ms}},
            )
            request_id_var.reset(token)
