"""StrikeOut King 9000 projection engine."""

from .projection_engine import ProjectionEngine, ProjectionResult

# The Odds API returns MLB event participants as full club names (for example,
# "Boston Red Sox"), while the projection app stores MLB abbreviations ("BOS").
# Normalize only the Odds API events-list response so the existing event matcher
# can reliably connect the MLB StatsAPI game to its Odds API event.
#
# This compatibility layer is intentionally limited to the events-list endpoint;
# event odds payloads are left untouched.
import requests as _requests

_TEAM_NAMES_TO_ABBR = {
    "Los Angeles Angels": "LAA", "Arizona Diamondbacks": "ARI", "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS", "Chicago Cubs": "CHC", "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE", "Colorado Rockies": "COL", "Detroit Tigers": "DET",
    "Houston Astros": "HOU", "Kansas City Royals": "KCR", "Los Angeles Dodgers": "LAD",
    "Washington Nationals": "WSH", "New York Mets": "NYM", "Oakland Athletics": "ATH",
    "Athletics": "ATH", "Pittsburgh Pirates": "PIT", "San Diego Padres": "SDP",
    "Seattle Mariners": "SEA", "San Francisco Giants": "SFG", "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TBR", "Texas Rangers": "TEX", "Toronto Blue Jays": "TOR",
    "Minnesota Twins": "MIN", "Philadelphia Phillies": "PHI", "Atlanta Braves": "ATL",
    "Chicago White Sox": "CHW", "Miami Marlins": "MIA", "New York Yankees": "NYY",
    "Milwaukee Brewers": "MIL",
}

_original_requests_get = _requests.get


def _normalize_odds_events_response(response):
    try:
        payload = response.json()
        if not isinstance(payload, list):
            return
        for event in payload:
            if not isinstance(event, dict):
                continue
            for field in ("home_team", "away_team"):
                name = str(event.get(field, "")).strip()
                abbr = _TEAM_NAMES_TO_ABBR.get(name)
                if abbr:
                    event[field] = abbr
        response._strikeout_king_normalized_json = payload
        response.json = lambda: response._strikeout_king_normalized_json
    except Exception:
        pass


def _requests_get_with_odds_event_normalization(url, *args, **kwargs):
    response = _original_requests_get(url, *args, **kwargs)
    url_text = str(url)
    if "/sports/baseball_mlb/events" in url_text and not "/events/" in url_text.rstrip("/").split("/events", 1)[-1]:
        _normalize_odds_events_response(response)
    return response


_requests.get = _requests_get_with_odds_event_normalization

__all__ = ["ProjectionEngine", "ProjectionResult"]
