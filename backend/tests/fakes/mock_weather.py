"""Offline weather with a few fixed scenarios, so demos and tests are deterministic."""
from datetime import date, timedelta
from typing import Literal

from app.schemas.weather import CurrentConditions, DayForecast, Forecast
from app.weather.provider import WeatherProvider

Scenario = Literal["mixed", "rain", "hot_dry"]


class MockWeatherProvider(WeatherProvider):
    name = "mock"

    def __init__(self, scenario: Scenario = "mixed", today: date | None = None):
        self.scenario = scenario
        self.today = today

    async def forecast(self, lat: float, lon: float) -> Forecast:
        start = self.today or date.today()

        def day(i: int, code: int, hi: float, lo: float, pct: int, mm: float, wind: float) -> DayForecast:
            return DayForecast(
                date=(start + timedelta(days=i)).isoformat(), condition_code=code,
                high_c=hi, low_c=lo, rain_chance_pct=pct, rain_mm=mm, wind_kph=wind,
            )

        if self.scenario == "rain":
            days = [day(0, 63, 28, 23, 85, 14.0, 12), day(1, 61, 28, 23, 70, 8.0, 10), day(2, 80, 29, 23, 75, 10.0, 14),
                    day(3, 61, 29, 23, 60, 5.0, 10), day(4, 3, 30, 24, 40, 1.5, 9)]
            return Forecast(lat=lat, lon=lon, current=CurrentConditions(temp_c=25, condition_code=63, wind_kph=12),
                            days=days, hourly_rain_chance_next_12h=[70, 80, 85, 85, 80, 75, 70, 60, 50, 40, 40, 30],
                            recent_rain_mm=30.0)
        if self.scenario == "hot_dry":
            days = [day(i, 0, 37, 25, 5, 0.0, 10) for i in range(5)]
            return Forecast(lat=lat, lon=lon, current=CurrentConditions(temp_c=34, condition_code=0, wind_kph=10),
                            days=days, hourly_rain_chance_next_12h=[0] * 12, recent_rain_mm=0.0)
        # "mixed": typical wet-season week in Akwa Ibom
        days = [day(0, 2, 31, 24, 20, 0.5, 11), day(1, 3, 30, 24, 35, 2.0, 12), day(2, 61, 29, 23, 70, 9.0, 15),
                day(3, 80, 29, 23, 65, 7.0, 14), day(4, 2, 31, 24, 15, 0.0, 10)]
        return Forecast(lat=lat, lon=lon, current=CurrentConditions(temp_c=29, condition_code=2, wind_kph=11),
                        days=days, hourly_rain_chance_next_12h=[20, 20, 25, 25, 25, 25, 40, 45, 50, 55, 60, 60],
                        recent_rain_mm=22.0)
