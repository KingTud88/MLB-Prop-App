from __future__ import annotations

import pandas as pd

from engine.weather_risk import WeatherDelayRisk

_EMPTY_UI_TOKENS = {"", "nan", "null", "nat", "<na>"}
_DISPLAY_ICONS = {
    "HIGH": "⛈️",
    "ELEVATED": "🌩️",
    "LOW": "🌧️",
    "NONE": "☀️",
    "ROOF": "🏟️",
}
_VALID_SAVED_LEVELS = set(_DISPLAY_ICONS)


def clean_ui_text(value: object, fallback: str = "") -> str:
    """Return display-safe scalar text without leaking pandas missing-value tokens."""
    try:
        if pd.isna(value):
            return fallback
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return fallback if text.lower() in _EMPTY_UI_TOKENS else text


def weather_icon_for_display(level: object, icon: object, *, unknown: str = "—") -> str:
    """Return a deterministic presentation icon while leaving raw weather semantics untouched."""
    explicit = clean_ui_text(icon)
    if explicit:
        return explicit
    normalized_level = clean_ui_text(level, "UNKNOWN").upper()
    return _DISPLAY_ICONS.get(normalized_level, unknown)


def _number(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def saved_weather_risk(frame: pd.DataFrame, game_pk: object, pitcher_id: object) -> WeatherDelayRisk | None:
    """Return the latest exact-game frozen weather snapshot for display fallback only."""
    if frame is None or frame.empty or not {"game_pk", "pitcher_id"}.issubset(frame.columns):
        return None
    game_value = _number(game_pk)
    pitcher_value = _number(pitcher_id)
    if game_value is None or pitcher_value is None:
        return None
    games = pd.to_numeric(frame["game_pk"], errors="coerce")
    pitchers = pd.to_numeric(frame["pitcher_id"], errors="coerce")
    matched = frame.loc[games.eq(game_value) & pitchers.eq(pitcher_value)].copy()
    if matched.empty:
        return None
    if "captured_at_utc" in matched.columns:
        matched["_captured"] = pd.to_datetime(matched["captured_at_utc"], errors="coerce", utc=True)
        matched = matched.sort_values("_captured", kind="stable", na_position="first")
    row = matched.iloc[-1]
    level = clean_ui_text(row.get("weather_delay_risk"), "UNKNOWN").upper()
    icon = clean_ui_text(row.get("weather_icon"))
    summary = clean_ui_text(row.get("weather_summary"), "Saved pregame weather snapshot.")
    available = level in _VALID_SAVED_LEVELS
    return WeatherDelayRisk(
        level,
        icon,
        _number(row.get("weather_precip_probability")),
        _number(row.get("weather_precip_mm")),
        None,
        summary,
        available,
    )
