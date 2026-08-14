from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

ODDS_API = "https://api.the-odds-api.com/v4"
EASTERN = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "data" / "odds_strikeout_snapshot.csv"
SNAPSHOT_COLUMNS = [
    "slate_date", "event_id", "commence_time", "home_team", "away_team",
    "pitcher", "book", "market", "name", "point", "price", "fetched_at_utc",
]


def resolve_api_key(secrets: object | None = None) -> str:
    for key in ("ODDS_API_KEY", "THE_ODDS_API_KEY", "odds_api_key"):
        try:
            if secrets is not None and key in secrets:
                value = str(secrets[key]).strip()
                if value:
                    return value
        except Exception:
            pass
    return str(os.getenv("ODDS_API_KEY") or os.getenv("THE_ODDS_API_KEY") or "").strip()


def _event_local_date(event: dict) -> str:
    raw = event.get("commence_time")
    ts = pd.to_datetime(raw, utc=True, errors="coerce")
    if pd.isna(ts):
        return ""
    return ts.tz_convert(EASTERN).date().isoformat()


def _quota(headers: requests.structures.CaseInsensitiveDict) -> dict[str, int | None]:
    def read(name: str) -> int | None:
        value = headers.get(name)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    return {
        "remaining": read("x-requests-remaining"),
        "used": read("x-requests-used"),
        "last": read("x-requests-last"),
    }


def _parse_event(event: dict, payload: dict, slate_date: str, fetched_at: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for bookmaker in payload.get("bookmakers", []) if isinstance(payload, dict) else []:
        for market in bookmaker.get("markets", []) or []:
            if market.get("key") != "pitcher_strikeouts":
                continue
            for outcome in market.get("outcomes", []) or []:
                pitcher = str(outcome.get("description") or "").strip()
                if not pitcher:
                    continue
                rows.append({
                    "slate_date": slate_date,
                    "event_id": str(event.get("id") or ""),
                    "commence_time": str(event.get("commence_time") or ""),
                    "home_team": str(event.get("home_team") or ""),
                    "away_team": str(event.get("away_team") or ""),
                    "pitcher": pitcher,
                    "book": bookmaker.get("title", bookmaker.get("key", "")),
                    "market": "pitcher_strikeouts",
                    "name": outcome.get("name"),
                    "point": outcome.get("point"),
                    "price": outcome.get("price"),
                    "fetched_at_utc": fetched_at,
                })
    return rows


def refresh_strikeout_snapshot(api_key: str, slate_date: str, *, session: requests.Session | None = None) -> tuple[pd.DataFrame, dict[str, int | None], str | None]:
    """Paid path: fetch only MLB pitcher_strikeouts after an explicit UI action."""
    key = str(api_key or "").strip()
    if not key:
        return pd.DataFrame(columns=SNAPSHOT_COLUMNS), {}, "Odds API key not found in Streamlit secrets."
    http = session or requests.Session()
    try:
        response = http.get(f"{ODDS_API}/sports/baseball_mlb/events", params={"apiKey": key}, timeout=15)
        response.raise_for_status()
        events = response.json()
    except (requests.RequestException, ValueError, TypeError) as exc:
        return pd.DataFrame(columns=SNAPSHOT_COLUMNS), {}, f"Odds API event lookup failed: {type(exc).__name__}."

    day_events = [event for event in events if isinstance(event, dict) and _event_local_date(event) == str(slate_date)]
    rows: list[dict[str, object]] = []
    quota: dict[str, int | None] = {}
    fetched_at = datetime.now(timezone.utc).isoformat()
    for event in day_events:
        try:
            response = http.get(
                f"{ODDS_API}/sports/baseball_mlb/events/{event.get('id')}/odds",
                params={"apiKey": key, "regions": "us", "markets": "pitcher_strikeouts", "oddsFormat": "american"},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            rows.extend(_parse_event(event, payload, str(slate_date), fetched_at))
            quota = _quota(response.headers)
        except (requests.RequestException, ValueError, TypeError):
            continue

    fresh = pd.DataFrame(rows, columns=SNAPSHOT_COLUMNS)
    existing = load_snapshot()
    if not existing.empty and "slate_date" in existing.columns:
        existing = existing.loc[~existing["slate_date"].astype(str).eq(str(slate_date))].copy()
    combined = pd.concat([existing, fresh], ignore_index=True) if not existing.empty else fresh.copy()
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(SNAPSHOT_PATH, index=False)
    return fresh, quota, None


def load_snapshot() -> pd.DataFrame:
    if not SNAPSHOT_PATH.exists():
        return pd.DataFrame(columns=SNAPSHOT_COLUMNS)
    try:
        frame = pd.read_csv(SNAPSHOT_PATH)
    except Exception:
        return pd.DataFrame(columns=SNAPSHOT_COLUMNS)
    for column in SNAPSHOT_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA
    return frame[SNAPSHOT_COLUMNS].copy()


def load_pitcher_strikeout_odds(pitcher_name: str, slate_date: str) -> list[dict[str, object]]:
    """Free path: disk-only read used by Main Projections; never calls the API."""
    frame = load_snapshot()
    if frame.empty:
        return []
    target = " ".join(str(pitcher_name).lower().split())
    names = frame["pitcher"].fillna("").astype(str).map(lambda value: " ".join(value.lower().split()))
    mask = frame["slate_date"].astype(str).eq(str(slate_date)) & names.eq(target)
    rows = frame.loc[mask].copy()
    for column in ("point", "price"):
        rows[column] = pd.to_numeric(rows[column], errors="coerce")
    return [
        {
            "book": row.get("book", ""),
            "market": "pitcher_strikeouts",
            "name": row.get("name"),
            "point": row.get("point"),
            "price": row.get("price"),
        }
        for _, row in rows.iterrows()
    ]
