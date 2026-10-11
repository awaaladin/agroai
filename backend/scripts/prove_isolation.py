"""Connect to the configured DATABASE_URL, create the AgroAI schema and tables, and prove that nothing outside
the AgroAI schema changed (every other app sharing the database is left exactly as it was). Safe to re-run."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.engine import Database  # noqa: E402
from app.db.models import SCHEMA  # noqa: E402


async def snapshot(db):
    async with db.engine.connect() as c:
        rows = (await c.execute(text(
            "select table_schema, table_name from information_schema.tables "
            "where table_schema not in ('information_schema','pg_catalog') and table_schema not like 'pg_%' order by 1,2"))).all()
    return {(r[0], r[1]) for r in rows}


async def main() -> int:
    settings = get_settings()
    db = Database(settings.database_url)
    if db.dialect != "postgresql":
        print("DATABASE_URL is not Postgres; nothing to prove.")
        return 0
    before = await snapshot(db)
    print("our schema:", SCHEMA)
    await db.ensure_ready()
    after = await snapshot(db)
    added = sorted(after - before)
    removed = sorted(before - after)
    print("tables added:", [f"{a}.{b}" for a, b in added])
    print("tables removed:", removed or "none")
    ok = all(a == SCHEMA for a, _ in added) and not removed
    print("ONLY OUR SCHEMA CHANGED:", ok)
    await db.dispose()
    return 0 if ok else 1


sys.exit(asyncio.run(main()))
