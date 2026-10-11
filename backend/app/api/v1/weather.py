from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.rate_limit import limit
from app.core.security import current_device
from app.schemas.weather import WeatherAdviceResponse
from app.services.crop_names import normalize_crop
from app.weather.advice_rules import evaluate

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/advice", response_model=WeatherAdviceResponse, dependencies=[Depends(limit("general"))])
async def weather_advice(
    request: Request,
    _device: Annotated[str, Depends(current_device)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    crop: Annotated[str | None, Query(max_length=40)] = None,
) -> WeatherAdviceResponse:
    """5-day summary plus deterministic farm guidance (the rules decide, the AI never does)."""
    try:
        forecast = await request.app.state.weather.forecast(lat, lon)
    except Exception:
        raise HTTPException(503, "The weather service is not answering. Please try again in a few minutes.")
    return WeatherAdviceResponse(
        lat=round(lat, 2), lon=round(lon, 2), current=forecast.current, days=forecast.days,
        advice=evaluate(forecast, normalize_crop(crop)),
    )
