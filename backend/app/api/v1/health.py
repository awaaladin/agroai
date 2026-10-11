from fastapi import APIRouter, Request
from sqlalchemy import text

router = APIRouter(tags=["health"])
VERSION = "0.1.0"


@router.get("/health")
async def health(request: Request) -> dict:
    try:
        redis_ok = bool(await request.app.state.redis.ping())
    except Exception:
        redis_ok = False
    try:
        async with request.app.state.db.session() as s:
            await s.execute(text("select 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if (redis_ok and db_ok) else "degraded",
        "database": request.app.state.db.dialect if db_ok else False,
        "version": VERSION,
        "redis": redis_ok,
        "vision_provider": request.app.state.vision.name,
        "weather_provider": request.app.state.weather.name,
    }
