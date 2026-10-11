"""App factory. Tests call create_app() with a fake store and mock providers."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app.ai.anthropic_provider import AnthropicProvider
from app.ai.gemini_provider import GeminiProvider
from app.ai.llm_provider import LLMProvider
from app.ai.stt import SpeechToTextProvider, build_stt
from app.ai.provider import ProviderError, VisionProvider
from app.api.v1 import auth, chat, diagnose, health, me, session, transcribe, weather
from app.core.config import Settings, get_settings
from app.core.logging import RequestContextMiddleware, setup_logging
from app.core.memory_store import MemoryStore
from app.db.engine import Database
from app.core.middleware import BodySizeLimitMiddleware, ReadyMiddleware, SecurityHeadersMiddleware
from app.core.rate_limit import RateLimited, RateLimiter, SpendCap
from app.services.accounts import AccountError, AccountService
from app.services.chat_service import ChatService
from app.services.diagnose_service import DiagnoseService
from app.services.session_store import SessionStore
from app.weather.open_meteo import OpenMeteoProvider
from app.weather.provider import WeatherProvider


def build_vision(settings: Settings) -> VisionProvider:
    if settings.vision_provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("VISION_PROVIDER=gemini needs GEMINI_API_KEY (free key: https://aistudio.google.com/apikey)")
        return GeminiProvider(settings)
    if not settings.anthropic_api_key:
        raise ValueError("VISION_PROVIDER=anthropic needs ANTHROPIC_API_KEY")
    return AnthropicProvider(settings)


def build_weather(settings: Settings, redis) -> WeatherProvider:
    return OpenMeteoProvider(redis, settings.open_meteo_url, settings.weather_cache_ttl_seconds,
                             settings.weather_timeout_seconds)


def build_store(settings: Settings):
    """Built-in memory store by default; a real Redis when REDIS_URL points at one."""
    if settings.redis_url.startswith("memory"):
        return MemoryStore()
    return Redis.from_url(settings.redis_url, decode_responses=True)


def create_app(
    settings: Settings | None = None,
    redis=None,
    vision: VisionProvider | None = None,
    weather_provider: WeatherProvider | None = None,
    stt: SpeechToTextProvider | None = None,
    db: Database | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    setup_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await app.state.db.ensure_ready()
        yield
        await app.state.redis.aclose()
        await app.state.db.dispose()

    app = FastAPI(title="AgroAI Advisor API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.redis = redis or build_store(settings)
    app.state.db = db or Database(settings.database_url)
    app.state.vision = vision or build_vision(settings)
    app.state.weather = weather_provider or build_weather(settings, app.state.redis)
    app.state.stt = stt or build_stt(settings)  # None when no Gemini key: /v1/transcribe answers 503
    app.state.limiter = RateLimiter(app.state.redis, settings)
    app.state.spend_cap = SpendCap(app.state.redis, settings.daily_ai_call_limit)
    if isinstance(app.state.vision, LLMProvider):
        app.state.vision.spend_cap = app.state.spend_cap  # mock providers cost nothing and are never capped
    if app.state.stt is not None:
        app.state.stt.spend_cap = app.state.spend_cap
    app.state.sessions = SessionStore(app.state.db, settings.session_ttl_seconds)
    app.state.accounts = AccountService(app.state.db, settings, app.state.redis)
    app.state.diagnose_service = DiagnoseService(app.state.vision, app.state.weather, app.state.sessions, app.state.accounts)
    app.state.chat_service = ChatService(app.state.vision, app.state.weather, app.state.sessions, app.state.accounts)

    @app.exception_handler(ProviderError)
    async def provider_error(_: Request, exc: ProviderError):
        return JSONResponse({"detail": exc.user_message}, status_code=exc.status_code)

    @app.exception_handler(AccountError)
    async def account_error(_: Request, exc: AccountError):
        return JSONResponse({"detail": exc.message, "detail_pcm": exc.message_pcm}, status_code=exc.status)

    @app.exception_handler(RateLimited)
    async def rate_limited(_: Request, exc: RateLimited):
        return JSONResponse(
            {"detail": exc.message, "detail_pcm": exc.message_pcm, "retry_after": exc.retry_after},
            status_code=429, headers={"Retry-After": str(exc.retry_after)},
        )

    # Each add_middleware wraps the previous, so the last one added is outermost.
    # Outside in: request context (ids, access log) > ready (database, knowledge) > security headers > CORS > body size > app.
    app.add_middleware(BodySizeLimitMiddleware, max_image_bytes=settings.max_image_bytes,
                       image_paths=("/v1/diagnose", "/v1/transcribe"))
    if settings.origins:
        app.add_middleware(
            CORSMiddleware, allow_origins=settings.origins, allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"], expose_headers=["Retry-After", "X-Request-ID"],
            allow_credentials=False, max_age=600,  # bearer tokens, not cookies, so no credentials
        )
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.env == "production")
    app.add_middleware(ReadyMiddleware, db=app.state.db, refresh_seconds=settings.knowledge_refresh_seconds)
    app.add_middleware(RequestContextMiddleware)

    for module in (health, auth, me, diagnose, chat, transcribe, weather, session):
        app.include_router(module.router, prefix="/v1")
    return app


app = create_app()  # `uvicorn app.main:app`; the store connects lazily, so importing is safe
