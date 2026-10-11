"""Open-Meteo forecast (free, no key). Cached 30 minutes per rounded lat/lon (Redis, shared across workers)."""
import logging

import httpx
from redis.asyncio import Redis

from app.schemas.weather import CurrentConditions, DayForecast, Forecast
from app.weather.provider import WeatherProvider

log = logging.getLogger("agroai.weather")

PAST_DAYS = 3
FORECAST_DAYS = 5
DAILY = ("weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
         "precipitation_sum,wind_speed_10m_max")


class OpenMeteoProvider(WeatherProvider):
    name = "open_meteo"

    def __init__(self, redis: Redis, base_url: str, cache_ttl: int = 1800, timeout: float = 8.0,
                 client: httpx.AsyncClient | None = None):
        self.redis = redis
        self.base_url = base_url
        self.cache_ttl = cache_ttl
        self.client = client or httpx.AsyncClient(timeout=timeout)

    @staticmethod
    def _key(lat: float, lon: float) -> str:
        return f"agroai:weather:{lat:.2f}:{lon:.2f}"

    async def forecast(self, lat: float, lon: float) -> Forecast:
        # Rounding to 2 decimals (~1 km) both shares the cache between nearby farms and avoids sending exact positions.
        lat, lon = round(lat, 2), round(lon, 2)
        key = self._key(lat, lon)
        cached = await self._cache_get(key)
        if cached is not None:
            return cached
        data = await self._fetch(lat, lon)
        forecast = parse_open_meteo(data, lat, lon)
        await self._cache_set(key, forecast)
        return forecast

    async def _fetch(self, lat: float, lon: float) -> dict:
        params = {
            "latitude": lat, "longitude": lon, "timezone": "auto", "wind_speed_unit": "kmh",
            "past_days": PAST_DAYS, "forecast_days": FORECAST_DAYS, "daily": DAILY,
            "current": "temperature_2m,weather_code,wind_speed_10m", "hourly": "precipitation_probability",
        }
        last: Exception | None = None
        for _ in range(2):  # one retry on a network hiccup
            try:
                r = await self.client.get(self.base_url, params=params)
                r.raise_for_status()
                return r.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                last = exc
        raise RuntimeError("open-meteo unavailable") from last

    async def _cache_get(self, key: str) -> Forecast | None:
        try:
            raw = await self.redis.get(key)
            return Forecast.model_validate_json(raw) if raw else None
        except Exception:
            return None  # a cache problem must never break weather

    async def _cache_set(self, key: str, forecast: Forecast) -> None:
        try:
            await self.redis.set(key, forecast.model_dump_json(), ex=self.cache_ttl)
        except Exception:
            log.warning("weather cache write failed")


def _num(v, default=0.0) -> float:
    return default if v is None else float(v)


def parse_open_meteo(data: dict, lat: float, lon: float) -> Forecast:
    """Turn Open-Meteo's response (3 past days + 5 forecast days) into our neutral Forecast."""
    d = data["daily"]
    past = PAST_DAYS
    days = [
        DayForecast(
            date=d["time"][i], condition_code=int(_num(d["weather_code"][i])),
            high_c=_num(d["temperature_2m_max"][i]), low_c=_num(d["temperature_2m_min"][i]),
            rain_chance_pct=int(_num(d["precipitation_probability_max"][i])),
            rain_mm=_num(d["precipitation_sum"][i]), wind_kph=_num(d["wind_speed_10m_max"][i]),
        )
        for i in range(past, past + FORECAST_DAYS)
    ]
    recent_rain = round(sum(_num(x) for x in d["precipitation_sum"][:past]), 1)

    cur = data["current"]
    current = CurrentConditions(temp_c=_num(cur["temperature_2m"]), condition_code=int(_num(cur["weather_code"])),
                                wind_kph=_num(cur["wind_speed_10m"]))

    # Next 12 hours of rain probability, starting from the current hour (times are local, ISO "YYYY-MM-DDTHH:MM").
    hours = data["hourly"]["time"]
    probs = data["hourly"]["precipitation_probability"]
    now_hour = cur["time"][:13]  # "YYYY-MM-DDTHH"
    start = next((i for i, t in enumerate(hours) if t[:13] >= now_hour), 0)
    next12 = [int(_num(p)) for p in probs[start:start + 12]]
    next12 += [next12[-1] if next12 else days[0].rain_chance_pct] * (12 - len(next12))

    return Forecast(lat=lat, lon=lon, current=current, days=days, hourly_rain_chance_next_12h=next12,
                    recent_rain_mm=recent_rain)
