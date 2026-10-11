from datetime import date, timedelta

from app.schemas.weather import CurrentConditions, DayForecast, Forecast
from app.weather.advice_rules import evaluate

TODAY = date(2026, 6, 1)


def day(i, hi=30, pct=10, mm=0.0, wind=8):
    return DayForecast(date=(TODAY + timedelta(days=i)).isoformat(), condition_code=2, high_c=hi, low_c=23,
                       rain_chance_pct=pct, rain_mm=mm, wind_kph=wind)


def forecast(days=None, hourly=None, recent=0.0, wind=8):
    return Forecast(
        lat=5.0, lon=7.9, current=CurrentConditions(temp_c=28, condition_code=2, wind_kph=wind),
        days=days or [day(i) for i in range(5)], hourly_rain_chance_next_12h=hourly or [10] * 12, recent_rain_mm=recent,
    )


def codes(items):
    return [i.code for i in items]


def test_rain_likely_within_6h_blocks_spraying():
    items = evaluate(forecast(hourly=[10, 10, 60, 10, 10, 10] + [10] * 6))
    assert "no_spray_rain_likely" in codes(items)
    assert "spray_ok" not in codes(items)
    assert items[0].severity == "warning"  # most urgent first


def test_rain_after_6h_does_not_block_spraying():
    items = evaluate(forecast(hourly=[10] * 6 + [90] * 6))
    assert "no_spray_rain_likely" not in codes(items) and "spray_ok" in codes(items)


def test_boundary_is_50_percent():
    assert "no_spray_rain_likely" in codes(evaluate(forecast(hourly=[50] + [0] * 11)))
    assert "no_spray_rain_likely" not in codes(evaluate(forecast(hourly=[49] + [0] * 11)))


def test_windy_day_advises_waiting_to_spray():
    items = evaluate(forecast(wind=30))
    assert "windy_no_spray" in codes(items) and "spray_ok" not in codes(items)


def test_planting_window_after_steady_rain():
    assert "planting_window" in codes(evaluate(forecast(recent=25)))
    assert "planting_window" not in codes(evaluate(forecast(recent=5)))
    # a downpour today is not a planting day
    assert "planting_window" not in codes(evaluate(forecast(days=[day(0, pct=90, mm=30)] + [day(i) for i in range(1, 5)], recent=25)))


def test_heat_warning_depends_on_crop():
    days = [day(0, hi=34), day(1, hi=34)] + [day(i) for i in range(2, 5)]
    assert "heat_warning" in codes(evaluate(forecast(days=days), crop="pepper"))  # pepper limit 33
    assert "heat_warning" not in codes(evaluate(forecast(days=days), crop="cassava"))  # cassava limit 38


def test_heat_beyond_three_days_is_ignored():
    days = [day(i) for i in range(3)] + [day(3, hi=40), day(4, hi=40)]
    assert "heat_warning" not in codes(evaluate(forecast(days=days), crop="maize"))


def test_dry_spell_severity_by_crop():
    dry = [day(i, pct=5) for i in range(5)]
    maize = next(i for i in evaluate(forecast(days=dry), crop="maize") if i.code == "dry_spell")
    cassava = next(i for i in evaluate(forecast(days=dry), crop="cassava") if i.code == "dry_spell")
    assert maize.severity == "warning" and cassava.severity == "info"


def test_no_dry_spell_when_rain_comes():
    days = [day(i, pct=5) for i in range(4)] + [day(4, pct=80, mm=12)]
    assert "dry_spell" not in codes(evaluate(forecast(days=days)))


def test_drying_days_listed():
    days = [day(0, pct=10), day(1, pct=70, mm=9), day(2, pct=15), day(3, pct=60, mm=5), day(4, pct=20)]
    item = next(i for i in evaluate(forecast(days=days)) if i.code == "drying_days")
    assert item.dates == [days[0].date, days[2].date, days[4].date]
    assert item.severity == "good"


def test_no_drying_days_when_wet():
    days = [day(i, pct=80, mm=10) for i in range(5)]
    assert "drying_days" not in codes(evaluate(forecast(days=days)))


def test_every_item_has_both_languages():
    for fc in (forecast(), forecast(hourly=[90] * 12, recent=30), forecast(days=[day(i, hi=40, pct=0) for i in range(5)])):
        for item in evaluate(fc, crop="maize"):
            assert item.message and item.message_pcm and item.message != item.message_pcm


def test_deterministic():
    f = forecast(hourly=[60] * 12, recent=30)
    assert evaluate(f, "yam") == evaluate(f, "yam")
