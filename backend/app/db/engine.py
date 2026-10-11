"""Database engine. SQLite locally (a file, no server); Postgres in production. Only DATABASE_URL changes.

    DATABASE_URL=sqlite+aiosqlite:///./agroai.db                       (default)
    DATABASE_URL=postgresql://user:pass@host:5432/dbname?sslmode=require   (Neon, Supabase, Render, ...)
"""
import uuid
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.pool import NullPool, StaticPool
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def normalize_url(url: str) -> str:
    """Accept the URLs hosting dashboards hand out and turn them into async-driver URLs.

    postgres://... and postgresql://... -> postgresql+asyncpg://...; sqlite:/// -> sqlite+aiosqlite:///.
    asyncpg does not understand libpq's sslmode=..., so it becomes ssl=... and unsupported libpq-only options are dropped.
    """
    if url.startswith("sqlite:"):
        return url.replace("sqlite:", "sqlite+aiosqlite:", 1)
    if url.startswith(("postgres://", "postgresql://")):
        url = "postgresql+asyncpg://" + url.split("://", 1)[1]
    if url.startswith("postgresql+asyncpg://"):
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query))
        sslmode = query.pop("sslmode", None)
        query.pop("channel_binding", None)  # libpq-only option some providers append
        if sslmode and sslmode != "disable" and "ssl" not in query:
            query["ssl"] = "require" if sslmode in {"require", "prefer", "allow"} else sslmode
        url = urlunsplit(parts._replace(query=urlencode(query)))
    return url


class Database:
    """Owns the engine and session factory. `ensure_ready` creates tables and seeds knowledge on first use."""

    def __init__(self, url: str):
        self.url = normalize_url(url)
        kwargs: dict = {}
        if self.url.startswith("postgresql"):
            # Hosted Postgres (Supabase, Neon) sits behind a transaction-mode pooler (pgbouncer), which cannot keep
            # prepared statements: turn the cache off and give each statement a unique name.
            kwargs = {
                "pool_size": 3, "max_overflow": 2, "pool_pre_ping": True, "pool_recycle": 300,
                "connect_args": {"statement_cache_size": 0, "prepared_statement_cache_size": 0,
                                 "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__"},
            }
        elif ":memory:" in self.url:
            kwargs = {"poolclass": StaticPool}  # one shared connection, or the in-memory database would vanish
        else:
            kwargs = {"poolclass": NullPool}  # SQLite file connections are cheap and this stays safe across event loops
        self.engine: AsyncEngine = create_async_engine(self.url, **kwargs)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self._ready = False

    @property
    def dialect(self) -> str:
        return self.engine.dialect.name

    def session(self) -> AsyncSession:
        return self.session_factory()

    async def ensure_ready(self) -> None:
        """Idempotent: create tables, seed the knowledge tables if empty, load the in-memory snapshot."""
        if self._ready:
            return
        from app.db.models import Base
        from app.db.seed import seed_if_empty
        from app.knowledge import reload_knowledge

        from sqlalchemy import text
        from app.db.models import SCHEMA

        async with self.engine.begin() as conn:
            if SCHEMA:  # Postgres: our own schema, created if missing. We never touch other schemas.
                await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
            await conn.run_sync(Base.metadata.create_all)
        await seed_if_empty(self)
        await reload_knowledge(self)
        self._ready = True

    async def dispose(self) -> None:
        await self.engine.dispose()
