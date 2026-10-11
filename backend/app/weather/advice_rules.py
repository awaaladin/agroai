"""Deterministic farm-weather rules. No AI here: the AI only *explains* what these return.

All thresholds are named constants so they are easy to review with an extension officer.
"""
from datetime import date

from app.schemas.weather import AdviceItem, Forecast

RAIN_LIKELY_PCT = 50  # rain this likely within 6 h -> do not spray or fertilize
CALM_RAIN_PCT = 30  # below this in the next 6 h -> spraying weather is fine
WINDY_KPH = 20  # spray drifts above this
PLANTING_RECENT_RAIN_MM = 20  # steady rain over the past 3 days
PLANTING_MAX_TODAY_RAIN_PCT = 80  # but not a downpour today
DRYING_MAX_RAIN_PCT = 20
DRYING_MAX_RAIN_MM = 1.0
DRY_SPELL_TOTAL_MM = 5.0
DRY_SPELL_MAX_RAIN_PCT = 30
HEAT_DAYS_CHECKED = 3

# Daytime high (deg C) above which the crop is stressed.
HEAT_THRESHOLD_C = {"maize": 35, "pepper": 33, "cocoyam": 34, "yam": 35, "plantain": 36, "cassava": 38}
DEFAULT_HEAT_THRESHOLD_C = 35

# Crops that suffer quickly in a dry spell (cassava and yam tolerate a short one).
DROUGHT_SENSITIVE = {"maize", "pepper", "cocoyam", "plantain"}

_SEVERITY_ORDER = {"warning": 0, "info": 1, "good": 2}


def _day_label(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%a %d")


def evaluate(forecast: Forecast, crop: str | None = None) -> list[AdviceItem]:
    """Return advice items, most urgent first. Same input always gives the same output."""
    crop = (crop or "").lower() or None
    items: list[AdviceItem] = []
    today = forecast.days[0]
    next6 = forecast.hourly_rain_chance_next_12h[:6]
    max6 = max(next6) if next6 else today.rain_chance_pct

    # Spraying / fertilizer
    if max6 >= RAIN_LIKELY_PCT:
        items.append(AdviceItem(
            code="no_spray_rain_likely", severity="warning",
            message="Rain is likely in the next few hours. Do not spray or put fertilizer today, the rain will wash it away.",
            message_pcm="Rain fit fall for the next few hours. No spray or put fertilizer today, the rain go wash am comot.",
        ))
    elif forecast.current.wind_kph > WINDY_KPH or today.wind_kph > WINDY_KPH:
        items.append(AdviceItem(
            code="windy_no_spray", severity="info",
            message="It is windy today. Wait for calmer air before spraying so it does not blow onto you or other crops.",
            message_pcm="Wind dey blow today. Wait make e calm before you spray so e no blow reach you or other crops.",
        ))
    elif max6 < CALM_RAIN_PCT:
        items.append(AdviceItem(
            code="spray_ok", severity="good",
            message="No rain is expected soon, so today is fine for spraying or fertilizer. Follow the label and wear protection.",
            message_pcm="Rain no go fall soon, so today good for spray or fertilizer. Follow wetin dey the label and wear protection.",
        ))

    # Planting window after steady rain
    if forecast.recent_rain_mm >= PLANTING_RECENT_RAIN_MM and today.rain_chance_pct < PLANTING_MAX_TODAY_RAIN_PCT:
        items.append(AdviceItem(
            code="planting_window", severity="good",
            message="The ground is wet after steady rain. This is a good time to plant if your crop is in season.",
            message_pcm="Ground don soak after steady rain. This na good time to plant if your crop dey season.",
        ))

    # Heat
    threshold = HEAT_THRESHOLD_C.get(crop, DEFAULT_HEAT_THRESHOLD_C)
    hot = [d for d in forecast.days[:HEAT_DAYS_CHECKED] if d.high_c >= threshold]
    if hot:
        labels = ", ".join(_day_label(d.date) for d in hot)
        items.append(AdviceItem(
            code="heat_warning", severity="warning", dates=[d.date for d in hot],
            message=f"Very hot days ahead ({labels}). Water young plants early morning or evening and mulch the soil.",
            message_pcm=f"Hot go too much ({labels}). Water small plants for early morning or evening and cover the soil with dry grass.",
        ))

    # Dry spell
    total_rain = sum(d.rain_mm for d in forecast.days)
    if total_rain < DRY_SPELL_TOTAL_MM and all(d.rain_chance_pct < DRY_SPELL_MAX_RAIN_PCT for d in forecast.days):
        sensitive = crop is None or crop in DROUGHT_SENSITIVE
        items.append(AdviceItem(
            code="dry_spell", severity="warning" if sensitive else "info",
            message="Little or no rain is expected for five days. Mulch to keep water in the soil" + (", and water if you can." if sensitive else "."),
            message_pcm="Rain no go fall well for five days. Cover the soil with dry grass make water stay" + (", and water am if you fit." if sensitive else "."),
        ))

    # Drying days for harvest
    dry_days = [d for d in forecast.days if d.rain_chance_pct <= DRYING_MAX_RAIN_PCT and d.rain_mm < DRYING_MAX_RAIN_MM]
    if dry_days:
        labels = ", ".join(_day_label(d.date) for d in dry_days)
        items.append(AdviceItem(
            code="drying_days", severity="good", dates=[d.date for d in dry_days],
            message=f"Good days to dry your harvest in the sun: {labels}.",
            message_pcm=f"Good days to dry your harvest for sun: {labels}.",
        ))

    return sorted(items, key=lambda i: _SEVERITY_ORDER[i.severity])
