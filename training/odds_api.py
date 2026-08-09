from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import requests

BASE_URL = "https://api.the-odds-api.com/v4"
SPORT_KEY = "baseball_mlb"
PLAYER_MARKET = "pitcher_strikeouts"


def get_api_key(secrets: Any = None) -> str | None:
    """Read the Odds API key from Streamlit secrets or an environment variable."""
    if secrets is not None:
        try:
            value = secrets.get("ODDS_API_KEY")
            if value:
                return str(value).strip()
        except Exception:
            pass
    value = os.getenv("ODDS_API_KEY")
    return value.strip() if value else None


class OddsAPIError(RuntimeError):
    pass


def _request(path: str, api_key: str, params: dict[str, Any]) -> tuple[Any, dict[str, str]]:
    query = dict(params)
    query["apiKey"] = api_key
    response = requests.get(f"{BASE_URL}{path}", params=query, timeout=20)
    if not response.ok:
        try:
            detail = response.json().get("message", response.text)
        except Exception:
            detail = response.text
        raise OddsAPIError(f"Odds API {response.status_code}: {detail}")
    return response.json(), {k.lower(): v for k, v in response.headers.items()}


def get_events(api_key: str, game_date: date) -> tuple[list[dict[str, Any]], dict[str, str]]:
    start = datetime.combine(game_date, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1) - timedelta(seconds=1)
    data, headers = _request(
        f"/sports/{SPORT_KEY}/events",
        api_key,
        {
            "dateFormat": "iso",
            "commenceTimeFrom": start.isoformat().replace("+00:00", "Z"),
            "commenceTimeTo": end.isoformat().replace("+00:00", "Z"),
        },
    )
    return list(data or []), headers


def get_event_pitcher_strikeouts(api_key: str, event_id: str, region: str = "us") -> tuple[dict[str, Any], dict[str, str]]:
    data, headers = _request(
        f"/sports/{SPORT_KEY}/events/{event_id}/odds",
        api_key,
        {
            "regions": region,
            "markets": PLAYER_MARKET,
            "oddsFormat": "american",
            "dateFormat": "iso",
        },
    )
    return dict(data or {}), headers


def flatten_pitcher_strikeouts(event: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bookmaker in event.get("bookmakers", []) or []:
        title = bookmaker.get("title") or bookmaker.get("key", "Unknown")
        for market in bookmaker.get("markets", []) or []:
            if market.get("key") != PLAYER_MARKET:
                continue
            for outcome in market.get("outcomes", []) or []:
                rows.append(
                    {
                        "bookmaker": title,
                        "bookmaker_key": bookmaker.get("key", ""),
                        "last_update": market.get("last_update", bookmaker.get("last_update", "")),
                        "side": outcome.get("name", ""),
                        "player": outcome.get("description", ""),
                        "line": outcome.get("point"),
                        "american_odds": outcome.get("price"),
                    }
                )
    return rows


def usage_summary(headers: dict[str, str]) -> dict[str, str]:
    return {
        "remaining": headers.get("x-requests-remaining", "unknown"),
        "used": headers.get("x-requests-used", "unknown"),
        "last_cost": headers.get("x-requests-last", "unknown"),
    }
