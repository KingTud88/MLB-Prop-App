from __future__ import annotations

"""Build leakage-safe historical pitcher snapshots from MLB Stats API data.

This module is intentionally conservative: if a pregame value cannot be
reconstructed from information dated before the target game, it is omitted
rather than backfilled from a current aggregate.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Iterable

import requests

from .snapshot_schema import PregameSnapshot, make_snapshot

API_ROOT = "https://statsapi.mlb.com/api/v1"


@dataclass(frozen=True)
class HistoricalGame:
    game_pk: str
    game_date: str
    home_team_id: int
    away_team_id: int
    home_team: str
    away_team: str


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.get(f"{API_ROOT}/{path.lstrip('/')}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def completed_games(start: date, end: date) -> list[HistoricalGame]:
    """Return completed MLB games in chronological order."""
    payload = _get("schedule", {"sportId": 1, "startDate": start.isoformat(), "endDate": end.isoformat(), "hydrate": "probablePitcher,team"})
    games: list[HistoricalGame] = []
    for day in payload.get("dates", []):
        for game in day.get("games", []):
            if game.get("status", {}).get("abstractGameState") != "Final":
                continue
            teams = game.get("teams", {})
            home = teams.get("home", {}).get("team", {})
            away = teams.get("away", {}).get("team", {})
            games.append(HistoricalGame(
                game_pk=str(game["gamePk"]),
                game_date=str(game.get("officialDate", day["date"])),
                home_team_id=int(home.get("id", 0)),
                away_team_id=int(away.get("id", 0)),
                home_team=str(home.get("name", "")),
                away_team=str(away.get("name", "")),
            ))
    return games


def game_feed(game_pk: str) -> dict[str, Any]:
    return _get(f"game/{game_pk}/feed/live")


def _started_pitcher(game: dict[str, Any], team_id: int) -> dict[str, Any] | None:
    players = game.get("liveData", {}).get("boxscore", {}).get("teams", {})
    side = "home" if team_id == game.get("gameData", {}).get("teams", {}).get("home", {}).get("id") else "away"
    roster = players.get(side, {}).get("players", {})
    for player in roster.values():
        stats = player.get("stats", {}).get("pitching", {})
        if stats.get("gamesStarted", 0) == 1:
            person = player.get("person", {})
            return {"id": person.get("id"), "name": person.get("fullName"), "throws": player.get("pitchHand", {}).get("code")}
    return None


def reconstruct_game(game_pk: str, historical_pitcher_stats: dict[str, dict[str, Any]]) -> list[PregameSnapshot]:
    """Reconstruct both starters using only the supplied pregame history.

    The caller is responsible for updating `historical_pitcher_stats` only
    after the game's outcome has been recorded. This ordering is the key
    leakage barrier.
    """
    game = game_feed(game_pk)
    gd = game.get("gameData", {})
    date_value = str(gd.get("datetime", {}).get("officialDate", ""))
    teams = gd.get("teams", {})
    live = game.get("liveData", {})
    box = live.get("boxscore", {}).get("teams", {})
    snapshots: list[PregameSnapshot] = []

    for side, opponent_side in (("home", "away"), ("away", "home")):
        team_id = teams.get(side, {}).get("id")
        opponent = teams.get(opponent_side, {}).get("name", "")
        starter = _started_pitcher(game, int(team_id)) if team_id else None
        if not starter or not starter.get("id"):
            continue

        pid = str(starter["id"])
        history = historical_pitcher_stats.get(pid, {})
        feature_payload = {
            "pitcher_k_pct": history.get("k_pct"),
            "historical_games": history.get("games", 0),
            "historical_k_sd": history.get("k_sd"),
            "hand": starter.get("throws"),
            "source": "mlb_statsapi_historical_reconstruction",
        }
        player = box.get(side, {}).get("players", {}).get(f"ID{pid}", {})
        pitching = player.get("stats", {}).get("pitching", {})
        outcome = pitching.get("strikeOuts")
        batters_faced = pitching.get("battersFaced")
        snapshots.append(make_snapshot(
            game_id=game_pk,
            game_date=date_value,
            pitcher_id=pid,
            pitcher_name=str(starter.get("name", "")),
            opponent_team=str(opponent),
            features=feature_payload,
            source_versions={"mlb_statsapi": "v1", "reconstruction": "1.0.0"},
            actual_strikeouts=int(outcome) if outcome is not None else None,
            actual_batters_faced=int(batters_faced) if batters_faced is not None else None,
        ))
    return snapshots


def date_chunks(start: date, end: date, days: int = 7) -> Iterable[tuple[date, date]]:
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=days - 1), end)
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)
