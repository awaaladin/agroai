"""Environment-driven settings. Every knob is an env var (see .env.example)."""
from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    jwt_secret: str = DEV_SECRET
    jwt_ttl_seconds: int = 24 * 3600
    user_token_ttl_seconds: int = 7 * 24 * 3600  # logged-in farmers stay signed in for a week
    login_max_failures: int = 5  # wrong PINs allowed per phone number per window
    login_window_seconds: int = 15 * 60
    redis_url: str = "memory://"  # "memory://" = built-in in-process store (no Redis needed); or redis://host:6379/0
    session_ttl_seconds: int = 30 * 60
    # SQLite file locally; set a postgresql://... URL to use Postgres (Neon, Supabase, Render...). Only this changes.
    database_url: str = "sqlite+aiosqlite:///./agroai.db"
    # Postgres only: keep every AgroAI table in its own schema so a shared database (other apps in "public")
    # is never touched. Ignored for SQLite.
    database_schema: str = "agroai"
    knowledge_refresh_seconds: int = 300  # how often edits to crop/safety rows in the database reach the running app
    allowed_origins: str = ""  # comma-separated exact browser origins; empty = no cross-origin browser access

    vision_provider: Literal["anthropic", "gemini"] = "gemini"  # real AI only; fakes live in tests/
    weather_provider: Literal["open_meteo"] = "open_meteo"
    anthropic_api_key: str = ""
    vision_model: str = "claude-sonnet-5-5"  # Anthropic model
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    # Tried in order when the main model is overloaded (503), rate limited (429) or retired (404).
    gemini_fallback_models: str = "gemini-3.6-flash,gemini-3.5-flash-lite"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_timeout_seconds: float = 60.0
    anthropic_timeout_seconds: float = 60.0
    anthropic_refusal_fallback: bool = True  # server-side fallback if the safety classifiers decline a request
    daily_ai_call_limit: int = 200  # global cap on paid AI calls per UTC day

    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_cache_ttl_seconds: int = 30 * 60
    weather_timeout_seconds: float = 8.0

    max_image_bytes: int = 5 * 1024 * 1024

    # Rate limits (fixed windows). Generous for one farmer, tight for scripts. Behind a proxy, set TRUSTED_PROXY_HOPS.
    rate_device_per_minute: int = 60
    rate_ip_per_minute: int = 120
    rate_diagnose_device_per_hour: int = 20  # the costly call
    rate_diagnose_ip_per_hour: int = 100  # many farmers can share one phone-network IP
    rate_chat_device_per_hour: int = 60
    rate_chat_ip_per_hour: int = 300
    rate_anon_ip_per_hour: int = 60  # token requests
    trusted_proxy_hops: int = 0  # 1 behind Render/Railway/Fly: use the client IP from X-Forwarded-For

    @property
    def gemini_models(self) -> list[str]:
        return [self.gemini_model, *[m.strip() for m in self.gemini_fallback_models.split(",") if m.strip()]]

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _production_safety(self) -> "Settings":
        if self.env == "production" and "*" in self.origins:
            raise ValueError("ALLOWED_ORIGINS must list exact origins in production, not *")
        if self.env == "production" and (self.jwt_secret == DEV_SECRET or len(self.jwt_secret) < 32):
            raise ValueError("JWT_SECRET must be a random string of at least 32 characters in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
