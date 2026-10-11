"""WeatherProvider interface plus a failure-tolerant helper used by diagnose and chat."""
import logging
from abc import ABC, abstractmethod

from app.schemas.weather import AdviceItem, Forecast
from app.weather.advice_rules import evaluate

log = logging.getLogger("agroai.weather")


class WeatherProvider(ABC):
    name: str

    @abstractmethod
    async def forecast(self, lat: float, lon: float) -> Forecast:
        """5-day forecast for the point (providers cache per rounded lat/lon)."""


async def advice_for(
    provider: WeatherProvider, lat: float | None, lon: float | None, crop: str | None
) -> list[AdviceItem] | None:
    """Rule-based advice, or None when there is no location or the weather service fails.

    Weather is a bonus: a failure here must never break a diagnosis.
    """
    if lat is None or lon is None:
        return None
    try:
        return evaluate(await provider.forecast(lat, lon), crop)
    except Exception:
        log.warning("weather lookup failed")
        return None


async def forecast_and_advice(
    provider: WeatherProvider, lat: float | None, lon: float | None, crop: str | None
) -> tuple[Forecast | None, list[AdviceItem] | None]:
    """The real forecast and the rule-based advice from it, or (None, None) with no location or a service failure."""
    if lat is None or lon is None:
        return None, None
    try:
        forecast = await provider.forecast(lat, lon)
        return forecast, evaluate(forecast, crop)
    except Exception:
        log.warning("weather lookup failed")
        return None, None
