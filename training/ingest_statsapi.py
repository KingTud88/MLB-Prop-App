from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "https://statsapi.mlb.com/api/v1"
USER_AGENT = "StrikeOut-King-9000/1.0"


def _get_json(path: str, params: dict[str, str]) -> dict[str, Any]:
    query = "&".join(f"{key}={value}" for key, value in params.items())
    request = Request(f"{BASE_URL}{path}?{query}", headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed trusted MLB API host
            return json.load(response)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"MLB Stats API request failed: {exc}") from exc


def fetch_schedule(start_date: date, end_date: date) -> list[dict[str, Any]]:
    """Fetch completed MLB games and probable-pitcher metadata for a date range."""
    payload = _get_json(
        "/schedule",
        {
            "sportId": "1",
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "hydrate": "probablePitcher,team",
        },
    )
    games: list[dict[str, Any]] = []
    for day in payload.get("dates", []):
        for game in day.get("games", []):
            if game.get("status", {}).get("abstractGameState") == "Final":
                games.append(game)
    return games


def fetch_boxscore(game_pk: int) -> dict[str, Any]:
    return _get_json(f"/game/{int(game_pk)}/boxscore", {})


def collect_completed_games(start_date: date, end_date: date, output: str | Path) -> Path:
    """Persist raw completed-game payloads for later snapshot reconstruction.

    This intentionally stores raw source payloads first. Feature engineering is
    a separate step so we never silently replace a historical pregame value with
    a current aggregate value.
    """
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    cursor = start_date
    while cursor <= end_date:
        games = fetch_schedule(cursor, cursor)
        for game in games:
            game_pk = game.get("gamePk")
            if game_pk is None:
                continue
            rows.append({"schedule": game, "boxscore": fetch_boxscore(int(game_pk))})
        cursor += timedelta(days=1)
    output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return output
