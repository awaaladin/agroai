"""Pure-ASGI middleware: security headers and request body size limits."""
import json

# Swagger UI loads its script and styles from jsDelivr, so the docs pages get a looser (but still bounded) CSP.
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
DOCS_CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; "
            "frame-ancestors 'none'; base-uri 'none'")


class SecurityHeadersMiddleware:
    def __init__(self, app, hsts: bool = False):
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        is_docs = scope["path"].startswith(DOCS_PATHS)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                extra = {
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                    b"referrer-policy": b"no-referrer",
                    b"permissions-policy": b"camera=(), microphone=(), geolocation=(), payment=()",
                    b"cross-origin-resource-policy": b"same-site",
                    b"content-security-policy": (DOCS_CSP if is_docs else API_CSP).encode(),
                }
                if not is_docs:
                    extra[b"cache-control"] = b"no-store"  # answers can contain farm and location details
                if self.hsts:
                    extra[b"strict-transport-security"] = b"max-age=31536000; includeSubDomains"
                present = {k.lower() for k, _ in headers}
                headers.extend((k, v) for k, v in extra.items() if k not in present)
            await send(message)

        await self.app(scope, receive, send_wrapper)


class BodySizeLimitMiddleware:
    """Reject oversized bodies early: by Content-Length when present, and by counting streamed bytes otherwise.

    The photo endpoint gets the image limit plus room for the other form fields; every other endpoint is small JSON.
    """

    def __init__(self, app, max_image_bytes: int, max_json_bytes: int = 64 * 1024,
                 image_paths: tuple[str, ...] = ("/v1/diagnose",)):
        self.app = app
        self.image_limit = max_image_bytes + 64 * 1024  # multipart framing and text fields
        self.json_limit = max_json_bytes
        self.image_paths = image_paths

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = self.image_limit if scope["path"] in self.image_paths else self.json_limit
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            return await self._too_large(send)

        received = 0
        too_big = False
        replaced = False

        async def counting_receive():
            nonlocal received, too_big
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    too_big = True
                    return {"type": "http.request", "body": b"", "more_body": False}  # stop feeding the app
            return message

        async def guarded_send(message):
            nonlocal replaced
            if too_big:
                if not replaced:  # the app saw a truncated body: whatever it answers, say 413 instead
                    replaced = True
                    await self._too_large(send)
                return
            await send(message)

        try:
            await self.app(scope, counting_receive, guarded_send)
        except Exception:
            if not too_big:
                raise
            if not replaced:  # the app choked on the truncated body: answer 413, not 500
                await self._too_large(send)

    @staticmethod
    async def _too_large(send):
        body = json.dumps({"detail": "That upload is too big. Please send a smaller file."}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})


class ReadyMiddleware:
    """Before the first request: create tables, seed and load knowledge. Afterwards: refresh knowledge every so often."""

    def __init__(self, app, db, refresh_seconds: int):
        self.app = app
        self.db = db
        self.refresh = refresh_seconds
        self._last = 0.0

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            import time
            from app.knowledge import reload_knowledge

            await self.db.ensure_ready()
            now = time.monotonic()
            if self._last == 0.0:
                self._last = now
            elif now - self._last >= self.refresh:
                self._last = now
                try:
                    await reload_knowledge(self.db)
                except Exception:  # a database blip must not take the API down; keep the last good snapshot
                    pass
        await self.app(scope, receive, send)
