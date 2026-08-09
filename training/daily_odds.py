from __future__ import annotations

from datetime import date
from typing import Any

from training.odds_api import OddsAPIError, flatten_pitcher_strikeouts, get_event_pitcher_strikeouts, get_events

_TEAM_NAMES = {
    "LAA":"Los Angeles Angels","ARI":"Arizona Diamondbacks","BAL":"Baltimore Orioles",
    "BOS":"Boston Red Sox","CHC":"Chicago Cubs","CIN":"Cincinnati Reds",
    "CLE":"Cleveland Guardians","COL":"Colorado Rockies","DET":"Detroit Tigers",
    "HOU":"Houston Astros","KCR":"Kansas City Royals","LAD":"Los Angeles Dodgers",
    "WSH":"Washington Nationals","NYM":"New York Mets","ATH":"Athletics",
    "PIT":"Pittsburgh Pirates","SDP":"San Diego Padres","SEA":"Seattle Mariners",
    "SFG":"San Francisco Giants","STL":"St. Louis Cardinals","TBR":"Tampa Bay Rays",
    "TEX":"Texas Rangers","TOR":"Toronto Blue Jays","MIN":"Minnesota Twins",
    "PHI":"Philadelphia Phillies","ATL":"Atlanta Braves","CHW":"Chicago White Sox",
    "MIA":"Miami Marlins","NYY":"New York Yankees","MIL":"Milwaukee Brewers",
}


def _matches(abbr: str, name: str) -> bool:
    target = _TEAM_NAMES.get(str(abbr).upper(), str(abbr)).lower()
    actual = str(name or "").lower()
    return target == actual or target in actual or actual in target


def enrich_daily_records(records: list[dict[str, Any]], api_key: str, slate_date: date) -> tuple[list[dict[str, Any]], list[str], dict[str, str]]:
    """Attach the best returned pitcher strikeout market to daily projection records.

    The caller opts into this because each event odds request consumes Odds API allowance.
    """
    if not records:
        return records, [], {}
    try:
        events, event_headers = get_events(api_key, slate_date)
    except OddsAPIError as exc:
        return records, [str(exc)], {}

    errors: list[str] = []
    out = [dict(record) for record in records]
    for record in out:
        event = next(
            (
                e for e in events
                if (_matches(record.get("team", ""), e.get("away_team")) and _matches(record.get("opponent", ""), e.get("home_team")))
                or (_matches(record.get("team", ""), e.get("home_team")) and _matches(record.get("opponent", ""), e.get("away_team")))
            ),
            None,
        )
        if event is None:
            errors.append(f"{record.get('player', 'Unknown')}: Odds API event match not found")
            continue
        try:
            payload, headers = get_event_pitcher_strikeouts(api_key, str(event["id"]), "us")
            rows = [
                row for row in flatten_pitcher_strikeouts(payload)
                if str(row.get("player", "")).strip().lower() == str(record.get("player", "")).strip().lower()
            ]
            if not rows:
                record["odds_market"] = "No pitcher strikeout market"
                continue
            # Prefer the most common sportsbook line returned for the pitcher.
            over_rows = [r for r in rows if str(r.get("side", "")).lower() == "over"]
            chosen = sorted(over_rows or rows, key=lambda r: (float(r.get("line") or 99), str(r.get("bookmaker") or "")))[0]
            record["odds_market"] = f"{chosen.get('side', '')} {chosen.get('line', '')} @ {int(chosen.get('american_odds', 0)):+d}"
            record["odds_bookmaker"] = str(chosen.get("bookmaker", ""))
            record["odds_line"] = chosen.get("line", "")
            record["odds_side"] = chosen.get("side", "")
            record["odds_price"] = chosen.get("american_odds", "")
            event_headers = headers or event_headers
        except (OddsAPIError, ValueError, TypeError) as exc:
            errors.append(f"{record.get('player', 'Unknown')}: {exc}")
    return out, errors, event_headers
