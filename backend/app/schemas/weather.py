from typing import Literal

from pydantic import BaseModel, Field


class CurrentConditions(BaseModel):
    temp_c: float
    condition_code: int  # WMO weather code
    wind_kph: float


class DayForecast(BaseModel):
    date: str  # ISO date
    condition_code: int  # WMO weather code
    high_c: float
    low_c: float
    rain_chance_pct: int = Field(ge=0, le=100)
    rain_mm: float = Field(ge=0)
    wind_kph: float = Field(ge=0)


class Forecast(BaseModel):
    """Provider-neutral forecast that the deterministic advice rules run on."""

    lat: float
    lon: float
    current: CurrentConditions
    days: list[DayForecast]  # today first, 5 days
    hourly_rain_chance_next_12h: list[int]  # % for each of the next 12 hours
    recent_rain_mm: float = 0.0  # rain over the previous 3 days


class AdviceItem(BaseModel):
    code: str
    severity: Literal["good", "info", "warning"]
    message: str  # English
    message_pcm: str  # Nigerian Pidgin
    dates: list[str] = []


class WeatherAdviceResponse(BaseModel):
    lat: float  # rounded to 2 decimals
    lon: float
    current: CurrentConditions
    days: list[DayForecast]
    advice: list[AdviceItem]
