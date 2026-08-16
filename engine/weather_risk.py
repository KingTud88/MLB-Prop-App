from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}
THUNDER_CODES = {95, 96, 99}


@dataclass(frozen=True)
class WeatherDelayRisk:
    level: str
    icon: str
    precip_probability: float | None
    precipitation_mm: float | None
    weather_code: int | None
    summary: str
    available: bool


def _empty(summary: str = "Weather forecast unavailable for this game window.") -> WeatherDelayRisk:
    return WeatherDelayRisk("UNKNOWN", "", None, None, None, summary, False)


def roof_protected(roof_type: object) -> bool:
    """Return whether MLB venue metadata describes a covered/closable roof."""
    text = str(roof_type or "").strip().lower()
    if not text or text == "open":
        return False
    return any(token in text for token in ("retract", "dome", "fixed roof", "closed roof"))


def apply_roof_protection(risk: WeatherDelayRisk, roof_type: object) -> WeatherDelayRisk:
    """Keep exterior weather visible while preventing false delay alarms under a roof.

    Retractable-roof parks still require a near-game roof-status check, so this
    is an informational protection label rather than a claim that the roof is
    definitely closed.
    """
    if not roof_protected(roof_type):
        return risk
    label = str(roof_type or "roof-capable").strip()
    exterior = str(risk.level or "UNKNOWN").upper()
    summary = (
        f"Roof-capable venue ({label}). Exterior weather is {exterior.lower()} but is not treated "
        "as an automatic pitcher-avoid delay signal; verify roof status near first pitch."
    )
    return WeatherDelayRisk(
        "ROOF", "🏟️", risk.precip_probability, risk.precipitation_mm, risk.weather_code, summary, True
    )


def assess_delay_risk(hourly: dict, game_time_utc: datetime) -> WeatherDelayRisk:
    """Classify rain/thunder risk from two hours before first pitch through four hours after.

    This is an informational delay-risk heuristic. It does not alter the baseball forecast.
    """
    if game_time_utc.tzinfo is None:
        game_time_utc = game_time_utc.replace(tzinfo=timezone.utc)
    else:
        game_time_utc = game_time_utc.astimezone(timezone.utc)

    times = pd.to_datetime(pd.Series(hourly.get("time", [])), utc=True, errors="coerce")
    probs = pd.to_numeric(pd.Series(hourly.get("precipitation_probability", [])), errors="coerce")
    precip = pd.to_numeric(pd.Series(hourly.get("precipitation", [])), errors="coerce")
    codes = pd.to_numeric(pd.Series(hourly.get("weather_code", [])), errors="coerce")
    n = min(len(times), len(probs), len(precip), len(codes))
    if n == 0:
        return _empty()

    start = game_time_utc - timedelta(hours=2)
    end = game_time_utc + timedelta(hours=4)
    frame = pd.DataFrame({
        "time": times.iloc[:n],
        "prob": probs.iloc[:n],
        "precip": precip.iloc[:n],
        "code": codes.iloc[:n],
    })
    frame = frame.loc[frame["time"].between(start, end)].copy()
    if frame.empty:
        return _empty("Weather forecast does not cover this game window yet.")

    max_prob = float(frame["prob"].max()) if frame["prob"].notna().any() else None
    max_precip = float(frame["precip"].max()) if frame["precip"].notna().any() else None
    numeric_codes = frame["code"].dropna().astype(int)
    code = int(numeric_codes.max()) if not numeric_codes.empty else None
    thunder = bool(numeric_codes.isin(THUNDER_CODES).any()) if not numeric_codes.empty else False
    rain = bool(numeric_codes.isin(RAIN_CODES).any()) if not numeric_codes.empty else False
    probability = max_prob or 0.0
    amount = max_precip or 0.0

    if thunder or probability >= 65.0 or amount >= 2.5:
        level, icon = "HIGH", "⛈️"
    elif (rain and probability >= 30.0) or probability >= 45.0 or amount >= 0.5:
        level, icon = "ELEVATED", "🌩️"
    elif rain or probability >= 20.0:
        level, icon = "LOW", "🌧️"
    else:
        level, icon = "NONE", ""

    pieces = [f"{level.title()} weather-delay risk"]
    if max_prob is not None:
        pieces.append(f"game-window precipitation probability up to {max_prob:.0f}%")
    if max_precip is not None and max_precip > 0:
        pieces.append(f"peak precipitation {max_precip:.1f} mm/h")
    if thunder:
        pieces.append("thunderstorm signal present")
    return WeatherDelayRisk(level, icon, max_prob, max_precip, code, " · ".join(pieces), True)


def fetch_weather_delay_risk(latitude: float, longitude: float, game_time_iso: str, timeout: int = 12) -> WeatherDelayRisk:
    try:
        game_time = pd.to_datetime(game_time_iso, utc=True, errors="coerce")
        if pd.isna(game_time):
            return _empty("Game time unavailable for weather risk.")
        response = requests.get(
            OPEN_METEO_FORECAST,
            params={
                "latitude": float(latitude),
                "longitude": float(longitude),
                "hourly": "precipitation_probability,precipitation,weather_code",
                "timezone": "UTC",
                "forecast_days": 16,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return _empty()
        return assess_delay_risk(payload.get("hourly", {}) or {}, game_time.to_pydatetime())
    except Exception:
        return _empty()
