from datetime import date, datetime, timedelta

import fakeredis
import httpx
import pytest

from app.weather.advice_rules import evaluate
from app.weather.open_meteo import OpenMeteoProvider, parse_open_meteo

TODAY = date(2026, 6, 10)
NOW = datetime(2026, 6, 10, 14, 30)


def payload(past_rain=(5.0, 10.0, 8.0), probs_by_hour=None):
    """Shape of Open-Meteo's response with past_days=3 and forecast_days=5 (8 daily rows, 8*24 hourly rows)."""
    days = [TODAY + timedelta(days=i) for i in range(-3, 5)]
    rain = list(past_rain) + [4.0, 12.0, 0.0, 0.0, 1.0]
    hours = [datetime.combine(d, datetime.min.time()) + timedelta(hours=h) for d in days for h in range(24)]
    probs = probs_by_hour or {}
    return {
        "current": {"time": NOW.strftime("%Y-%m-%dT%H:%M"), "temperature_2m": 29.4, "weather_code": 3, "wind_speed_10m": 11.2},
        "daily": {
            "time": [d.isoformat() for d in days],
            "weather_code": [61, 63, 61, 3, 80, 1, 2, 3],
            "temperature_2m_max": [28, 28, 29, 31, 30, 32, 33, 31],
            "temperature_2m_min": [23] * 8,
            "precipitation_probability_max": [None, None, None, 40, 80, 5, 10, 25],
            "precipitation_sum": rain,
            "wind_speed_10m_max": [10, 11, 12, 13, 14, 15, 16, 17],
        },
        "hourly": {
            "time": [h.strftime("%Y-%m-%dT%H:%M") for h in hours],
            "precipitation_probability": [probs.get(h, 20) for h in hours],
        },
    }


def test_parse_picks_the_five_forecast_days_and_sums_past_rain():
    f = parse_open_meteo(payload(), 5.05, 7.91)
    assert [d.date for d in f.days] == [(TODAY + timedelta(days=i)).isoformat() for i in range(5)]
    assert f.days[0].rain_chance_pct == 40 and f.days[1].rain_mm == 12.0 and f.days[0].high_c == 31
    assert f.recent_rain_mm == 23.0
    assert (f.current.temp_c, f.current.condition_code, f.current.wind_kph) == (29.4, 3, 11.2)


def test_next_12_hours_start_at_the_current_hour():
    probs = {datetime(2026, 6, 10, 13): 99, datetime(2026, 6, 10, 14): 71, datetime(2026, 6, 10, 15): 72}
    f = parse_open_meteo(payload(probs_by_hour=probs), 5.05, 7.91)
    assert len(f.hourly_rain_chance_next_12h) == 12
    assert f.hourly_rain_chance_next_12h[:2] == [71, 72]  # 14:00 and 15:00, not the past 13:00


def test_rules_run_on_a_parsed_forecast():
    codes = [i.code for i in evaluate(parse_open_meteo(payload(), 5.05, 7.91), "maize")]
    assert "planting_window" in codes and "drying_days" in codes


class Counter:
    """httpx transport that returns a canned payload and counts calls."""

    def __init__(self, responder=None):
        self.calls = []
        self.responder = responder or (lambda req: httpx.Response(200, json=payload()))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(dict(request.url.params))
        return self.responder(request)


def make_provider(counter, redis=None):
    client = httpx.AsyncClient(transport=httpx.MockTransport(counter))
    return OpenMeteoProvider(redis or fakeredis.FakeAsyncRedis(decode_responses=True), "https://example.test/v1/forecast",
                             client=client)


async def test_request_params():
    c = Counter()
    await make_provider(c).forecast(5.0517, 7.9128)
    q = c.calls[0]
    assert q["latitude"] == "5.05" and q["longitude"] == "7.91"  # rounded: exact position is never sent
    assert q["past_days"] == "3" and q["forecast_days"] == "5" and q["timezone"] == "auto" and q["wind_speed_unit"] == "kmh"
    assert "precipitation_probability_max" in q["daily"]


async def test_cached_for_30_minutes_per_rounded_location():
    c, redis = Counter(), fakeredis.FakeAsyncRedis(decode_responses=True)
    p = make_provider(c, redis)
    await p.forecast(5.0517, 7.9128)
    await p.forecast(5.0549, 7.9101)  # same 2-decimal cell (5.05, 7.91)
    await p.forecast(5.05, 7.91)
    assert len(c.calls) == 1
    assert 1700 < await redis.ttl("agroai:weather:5.05:7.91") <= 1800
    await p.forecast(6.00, 7.91)  # different cell
    assert len(c.calls) == 2


async def test_cache_expiry_refetches():
    c, redis = Counter(), fakeredis.FakeAsyncRedis(decode_responses=True)
    p = make_provider(c, redis)
    await p.forecast(5.05, 7.91)
    await redis.delete("agroai:weather:5.05:7.91")
    await p.forecast(5.05, 7.91)
    assert len(c.calls) == 2


async def test_one_retry_on_network_error_then_success():
    state = {"n": 0}

    def flaky(req):
        state["n"] += 1
        if state["n"] == 1:
            raise httpx.ConnectError("down", request=req)
        return httpx.Response(200, json=payload())

    c = Counter(flaky)
    assert (await make_provider(c).forecast(5.05, 7.91)).days
    assert state["n"] == 2


async def test_service_error_raises_and_is_not_cached():
    c = Counter(lambda req: httpx.Response(503))
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    with pytest.raises(RuntimeError):
        await make_provider(c, redis).forecast(5.05, 7.91)
    assert await redis.get("agroai:weather:5.05:7.91") is None


async def test_broken_cache_does_not_break_weather():
    class BrokenRedis:
        async def get(self, *a, **k): raise ConnectionError
        async def set(self, *a, **k): raise ConnectionError

    p = OpenMeteoProvider(BrokenRedis(), "https://example.test/v1/forecast",
                          client=httpx.AsyncClient(transport=httpx.MockTransport(Counter())))
    assert (await p.forecast(5.05, 7.91)).days
