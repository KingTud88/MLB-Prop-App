from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

import pandas as pd
import requests

API_BASE = "https://api.sportsgameodds.com/v2"
PROVIDER = "SPORTSGAMEODDS"
EASTERN = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "data" / "sportsgameodds_snapshot.csv"
HISTORY_PATH = ROOT / "data" / "sportsbook_line_history.csv"
STATUS_PATH = ROOT / "data" / "sportsgameodds_status.json"
PROJECTION_LOG_PATH = ROOT / "data" / "projection_log.csv"

BOOK_PRIORITY = ("espnbet", "fanduel", "draftkings", "betmgm", "caesars")
BOOK_NAMES = {
    "espnbet": "ESPN BET",
    "fanduel": "FanDuel",
    "draftkings": "DraftKings",
    "betmgm": "BetMGM",
    "caesars": "Caesars",
}
STAT_TO_MARKET = {
    "pitching_strikeouts": "pitcher_strikeouts",
    "pitching_outs": "pitcher_outs",
    "pitching_hits": "pitcher_hits_allowed",
}
MARKET_TO_ACTIVE_COLUMNS = {
    "pitcher_strikeouts": ("active_strikeout_line", "active_strikeout_line_source"),
    "pitcher_outs": ("active_outs_line", "active_outs_line_source"),
    "pitcher_hits_allowed": ("active_hits_allowed_line", "active_hits_allowed_line_source"),
}
ODD_TEMPLATES = tuple(f"{stat}-PLAYER_ID-game-ou-over" for stat in STAT_TO_MARKET)
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (0.25, 0.50)
MAX_SNAPSHOT_AGE = timedelta(hours=6)

OFFER_COLUMNS = [
    "slate_date", "event_id", "commence_time", "home_team", "away_team",
    "player_id", "pitcher", "market", "side", "point", "price",
    "bookmaker_id", "book", "provider", "book_last_updated_at", "deeplink",
    "fetched_at_utc",
]


def resolve_api_key(secrets: object | None = None) -> str:
    for key in ("SPORTSGAMEODDS_API_KEY", "SPORTS_GAME_ODDS_API_KEY"):
        try:
            if secrets is not None and key in secrets:
                value = str(secrets[key]).strip()
                if value:
                    return value
        except Exception:
            pass
    return str(os.getenv("SPORTSGAMEODDS_API_KEY") or os.getenv("SPORTS_GAME_ODDS_API_KEY") or "").strip()


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def _normalize_name(value: object) -> str:
    return " ".join(str(value or "").lower().split())


def _team_name(event: dict, side: str) -> str:
    team = (event.get("teams") or {}).get(side) or {}
    names = team.get("names") or {}
    return str(names.get("long") or names.get("medium") or names.get("short") or team.get("name") or "").strip()


def _player_name(event: dict, player_id: str) -> str:
    player = (event.get("players") or {}).get(player_id) or {}
    names = player.get("names") or {}
    return str(player.get("name") or names.get("display") or "").strip()


def _event_start(event: dict) -> pd.Timestamp | None:
    raw = (event.get("status") or {}).get("startsAt")
    stamp = pd.to_datetime(raw, utc=True, errors="coerce")
    return None if pd.isna(stamp) else stamp


def _slate_window_utc(slate_date: str) -> tuple[str, str]:
    day = date.fromisoformat(str(slate_date))
    start_local = datetime.combine(day, dt_time.min, EASTERN)
    end_local = start_local + timedelta(days=1)
    return (
        start_local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        end_local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    )


def _safe_get_json(
    http: requests.Session,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, object],
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[dict | None, str | None]:
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = http.get(url, headers=headers, params=params, timeout=20)
        except (requests.Timeout, requests.ConnectionError):
            if attempt < MAX_ATTEMPTS - 1:
                sleep(BACKOFF_SECONDS[attempt])
                continue
            return None, "SportsGameOdds temporarily unavailable after connection retries."
        except requests.RequestException:
            return None, "SportsGameOdds request failed."

        status = int(getattr(response, "status_code", 200) or 200)
        if status in RETRYABLE_STATUS_CODES and attempt < MAX_ATTEMPTS - 1:
            sleep(BACKOFF_SECONDS[attempt])
            continue
        if status >= 400:
            return None, f"SportsGameOdds request failed with HTTP {status}."
        try:
            payload = response.json()
        except (TypeError, ValueError):
            return None, "SportsGameOdds returned invalid JSON."
        if not isinstance(payload, dict):
            return None, "SportsGameOdds returned an unexpected response."
        if payload.get("success") is False:
            return None, "SportsGameOdds returned success=false."
        return payload, None
    return None, "SportsGameOdds request exhausted retries."


def _parse_event_offers(event: dict, slate_date: str, fetched_at_utc: str) -> list[dict[str, object]]:
    start = _event_start(event)
    if start is None or start.tz_convert(EASTERN).date().isoformat() != str(slate_date):
        return []
    status = event.get("status") or {}
    if _truthy(status.get("started")) or _truthy(status.get("ended")) or _truthy(status.get("cancelled")):
        return []

    rows: list[dict[str, object]] = []
    odds = event.get("odds") or {}
    if not isinstance(odds, dict):
        return rows
    for odd in odds.values():
        if not isinstance(odd, dict):
            continue
        stat_id = str(odd.get("statID") or "")
        market = STAT_TO_MARKET.get(stat_id)
        side = str(odd.get("sideID") or "").lower()
        player_id = str(odd.get("playerID") or odd.get("statEntityID") or "").strip()
        if not market or side not in {"over", "under"} or not player_id:
            continue
        if str(odd.get("periodID") or "") != "game" or str(odd.get("betTypeID") or "") != "ou":
            continue
        pitcher = _player_name(event, player_id)
        if not pitcher:
            continue
        by_book = odd.get("byBookmaker") or {}
        if not isinstance(by_book, dict):
            continue
        for bookmaker_id in BOOK_PRIORITY:
            book_data = by_book.get(bookmaker_id)
            if not isinstance(book_data, dict) or not _truthy(book_data.get("available")):
                continue
            point = _number(book_data.get("overUnder"))
            price = _number(book_data.get("odds"))
            if point is None or price is None:
                continue
            rows.append({
                "slate_date": str(slate_date),
                "event_id": str(event.get("eventID") or ""),
                "commence_time": start.isoformat(),
                "home_team": _team_name(event, "home"),
                "away_team": _team_name(event, "away"),
                "player_id": player_id,
                "pitcher": pitcher,
                "market": market,
                "side": side.title(),
                "point": point,
                "price": price,
                "bookmaker_id": bookmaker_id,
                "book": BOOK_NAMES.get(bookmaker_id, bookmaker_id),
                "provider": PROVIDER,
                "book_last_updated_at": str(book_data.get("lastUpdatedAt") or ""),
                "deeplink": str(book_data.get("deeplink") or ""),
                "fetched_at_utc": fetched_at_utc,
            })
    return rows


def fetch_slate_offers(
    api_key: str,
    slate_date: str,
    *,
    session: requests.Session | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[pd.DataFrame, dict[str, object], str | None]:
    key = str(api_key or "").strip()
    if not key:
        return pd.DataFrame(columns=OFFER_COLUMNS), {}, "SPORTSGAMEODDS_API_KEY is not configured."

    start_utc, end_utc = _slate_window_utc(slate_date)
    http = session or requests.Session()
    headers = {"x-api-key": key}
    base_params: dict[str, object] = {
        "leagueID": "MLB",
        "type": "match",
        "oddsAvailable": "true",
        "started": "false",
        "ended": "false",
        "startsAfter": start_utc,
        "startsBefore": end_utc,
        "oddID": ",".join(ODD_TEMPLATES),
        "includeOpposingOdds": "true",
        "includeAltLines": "false",
        "bookmakerID": ",".join(BOOK_PRIORITY),
        "limit": 100,
    }
    fetched_at = datetime.now(timezone.utc).isoformat()
    cursor: str | None = None
    all_events: list[dict] = []
    notices: list[str] = []
    pages = 0
    while True:
        params = dict(base_params)
        if cursor:
            params["cursor"] = cursor
        payload, error = _safe_get_json(http, f"{API_BASE}/events", headers=headers, params=params, sleep=sleep)
        if error:
            return pd.DataFrame(columns=OFFER_COLUMNS), {
                "provider": PROVIDER,
                "slate_date": str(slate_date),
                "fetched_at_utc": fetched_at,
                "pages": pages,
                "event_count": len(all_events),
                "notice": " | ".join(notices),
                "error": error,
            }, error
        pages += 1
        data = payload.get("data") or []
        if isinstance(data, list):
            all_events.extend(event for event in data if isinstance(event, dict))
        notice = payload.get("notice")
        if notice:
            notices.append(str(notice))
        cursor = str(payload.get("nextCursor") or "").strip() or None
        if not cursor:
            break
        if pages >= 5:
            return pd.DataFrame(columns=OFFER_COLUMNS), {
                "provider": PROVIDER,
                "slate_date": str(slate_date),
                "fetched_at_utc": fetched_at,
                "pages": pages,
                "event_count": len(all_events),
                "notice": " | ".join(notices),
                "error": "SportsGameOdds pagination exceeded safety limit.",
            }, "SportsGameOdds pagination exceeded safety limit."

    rows: list[dict[str, object]] = []
    for event in all_events:
        rows.extend(_parse_event_offers(event, str(slate_date), fetched_at))
    offers = pd.DataFrame(rows, columns=OFFER_COLUMNS)
    if not offers.empty:
        offers = offers.drop_duplicates().reset_index(drop=True)
    metadata = {
        "provider": PROVIDER,
        "slate_date": str(slate_date),
        "fetched_at_utc": fetched_at,
        "pages": pages,
        "event_count": len(all_events),
        "offer_count": int(len(offers)),
        "notice": " | ".join(dict.fromkeys(notices)),
        "error": "",
    }
    return offers, metadata, None


def select_preferred_book_pairs(offers: pd.DataFrame) -> pd.DataFrame:
    """Keep one authentic, complete O/U pair per pitcher/market.

    ESPN BET is preferred. A fallback book is used only if both available sides
    are present on the exact same line. Consensus/fair lines are never used.
    """
    if offers is None or offers.empty:
        return pd.DataFrame(columns=OFFER_COLUMNS)
    work = offers.copy()
    work["point"] = pd.to_numeric(work["point"], errors="coerce")
    work["price"] = pd.to_numeric(work["price"], errors="coerce")
    selected: list[pd.DataFrame] = []
    keys = ["slate_date", "event_id", "player_id", "pitcher", "market"]
    for _, group in work.groupby(keys, dropna=False, sort=False):
        for bookmaker_id in BOOK_PRIORITY:
            book = group.loc[group["bookmaker_id"].astype(str).eq(bookmaker_id)].copy()
            if book.empty:
                continue
            over = book.loc[book["side"].astype(str).str.lower().eq("over")]
            under = book.loc[book["side"].astype(str).str.lower().eq("under")]
            if over.empty or under.empty:
                continue
            common = sorted(set(over["point"].dropna().astype(float)) & set(under["point"].dropna().astype(float)))
            if not common:
                continue
            point = common[0]
            pair = pd.concat([
                over.loc[over["point"].eq(point)].head(1),
                under.loc[under["point"].eq(point)].head(1),
            ], ignore_index=True)
            if len(pair) == 2:
                selected.append(pair)
                break
    if not selected:
        return pd.DataFrame(columns=OFFER_COLUMNS)
    return pd.concat(selected, ignore_index=True)[OFFER_COLUMNS].copy()


def _read_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)
    try:
        frame = pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=columns)
    for column in columns:
        if column not in frame.columns:
            frame[column] = pd.NA
    return frame[columns].copy()


def persist_capture(
    offers: pd.DataFrame,
    metadata: dict[str, object],
    *,
    snapshot_path: Path = SNAPSHOT_PATH,
    history_path: Path = HISTORY_PATH,
    status_path: Path = STATUS_PATH,
) -> pd.DataFrame:
    selected = select_preferred_book_pairs(offers)
    slate_date = str(metadata.get("slate_date") or "")
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    existing_snapshot = _read_csv(snapshot_path, OFFER_COLUMNS)
    if slate_date and not existing_snapshot.empty:
        existing_snapshot = existing_snapshot.loc[~existing_snapshot["slate_date"].astype(str).eq(slate_date)].copy()
    combined_snapshot = pd.concat([existing_snapshot, selected], ignore_index=True) if not existing_snapshot.empty else selected.copy()
    combined_snapshot.to_csv(snapshot_path, index=False)

    existing_history = _read_csv(history_path, OFFER_COLUMNS)
    combined_history = pd.concat([existing_history, offers], ignore_index=True) if not existing_history.empty else offers.copy()
    if not combined_history.empty:
        combined_history = combined_history.drop_duplicates().reset_index(drop=True)
    combined_history.to_csv(history_path, index=False)

    status = dict(metadata)
    status.update({
        "selected_offer_count": int(len(selected)),
        "selected_pair_count": int(len(selected) // 2),
        "selected_pitchers": int(selected["pitcher"].nunique()) if not selected.empty else 0,
        "selected_markets": sorted(selected["market"].dropna().astype(str).unique().tolist()) if not selected.empty else [],
        "production_authority": "MARKET_INPUT_ONLY",
        "projection_adjustment": False,
        "consensus_line_fallback": False,
    })
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True), encoding="utf-8")
    return selected


def apply_selected_lines_to_projection_log(
    frame: pd.DataFrame,
    selected: pd.DataFrame,
    slate_date: str,
) -> tuple[pd.DataFrame, int]:
    if frame is None or frame.empty or selected is None or selected.empty or "game_date" not in frame.columns:
        return (pd.DataFrame() if frame is None else frame.copy()), 0
    work = frame.copy()
    for line_col, source_col in MARKET_TO_ACTIVE_COLUMNS.values():
        if line_col not in work.columns:
            work[line_col] = pd.NA
        if source_col not in work.columns:
            work[source_col] = ""
    chosen = select_preferred_book_pairs(selected)
    if chosen.empty:
        return work, 0

    applied = 0
    day_mask = work["game_date"].astype(str).eq(str(slate_date))
    for idx in work.index[day_mask]:
        player = _normalize_name(work.at[idx, "player"] if "player" in work.columns else "")
        if not player:
            continue
        pitcher_rows = chosen.loc[chosen["pitcher"].map(_normalize_name).eq(player)]
        for market, (line_col, source_col) in MARKET_TO_ACTIVE_COLUMNS.items():
            current_source = str(work.at[idx, source_col] or "").upper()
            if current_source == "MANUAL":
                continue
            market_rows = pitcher_rows.loc[pitcher_rows["market"].astype(str).eq(market)]
            if market_rows.empty:
                continue
            start = pd.to_datetime(market_rows.iloc[0].get("commence_time"), utc=True, errors="coerce")
            captured = pd.to_datetime(market_rows.iloc[0].get("fetched_at_utc"), utc=True, errors="coerce")
            if pd.isna(start) or pd.isna(captured) or captured >= start:
                continue
            points = pd.to_numeric(market_rows["point"], errors="coerce").dropna().unique()
            if len(points) != 1:
                continue
            book = str(market_rows.iloc[0].get("book") or "").strip()
            work.at[idx, line_col] = float(points[0])
            work.at[idx, source_col] = f"SPORTSGAMEODDS · {book}" if book else PROVIDER
            applied += 1
    return work, applied


def _market_odds_rows(rows: pd.DataFrame) -> list[dict[str, object]]:
    if rows.empty:
        return []
    work = rows.copy()
    work["point"] = pd.to_numeric(work["point"], errors="coerce")
    work["price"] = pd.to_numeric(work["price"], errors="coerce")
    work = work.loc[work["point"].notna() & work["price"].notna()]
    return [
        {
            "book": row.get("book", ""),
            "market": row.get("market", ""),
            "name": row.get("side", ""),
            "point": float(row.get("point")),
            "price": float(row.get("price")),
            "provider": str(row.get("provider") or PROVIDER),
            "bookmaker_id": row.get("bookmaker_id", ""),
            "fetched_at_utc": row.get("fetched_at_utc", ""),
        }
        for _, row in work.iterrows()
    ]


def load_pitcher_market_odds(
    pitcher_name: str,
    slate_date: str,
    *,
    snapshot_path: Path = SNAPSHOT_PATH,
    now_utc: datetime | None = None,
) -> list[dict[str, object]]:
    """Disk-only app loader. Stale snapshots fail closed instead of masquerading as live lines."""
    frame = _read_csv(snapshot_path, OFFER_COLUMNS)
    if frame.empty:
        return []
    target = _normalize_name(pitcher_name)
    names = frame["pitcher"].map(_normalize_name)
    rows = frame.loc[frame["slate_date"].astype(str).eq(str(slate_date)) & names.eq(target)].copy()
    if rows.empty:
        return []
    fetched = pd.to_datetime(rows["fetched_at_utc"], utc=True, errors="coerce")
    newest = fetched.max()
    now = pd.Timestamp(now_utc or datetime.now(timezone.utc))
    if pd.isna(newest) or now - newest > MAX_SNAPSHOT_AGE:
        return []
    return _market_odds_rows(rows)
