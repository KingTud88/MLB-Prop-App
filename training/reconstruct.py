from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import requests

from .snapshot_schema import PregameSnapshot, make_snapshot

MLB_API = "https://statsapi.mlb.com/api/v1"


@dataclass(frozen=True)
class ReconstructionConfig:
    season: int
    start_date: date
    end_date: date
    timeout: int = 20


class StatsApi:
    def __init__(self, timeout: int = 20) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "StrikeOutKing9000/1.0"})
        self.timeout = timeout

    def get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self.session.get(f"{MLB_API}/{endpoint}", params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("MLB Stats API returned a non-object response")
        return payload


def _game_rows(api: StatsApi, cfg: ReconstructionConfig) -> list[dict[str, Any]]:
    payload = api.get("schedule", {
        "sportId": 1,
        "startDate": cfg.start_date.isoformat(),
        "endDate": cfg.end_date.isoformat(),
        "gameTypes": "R",
        "hydrate": "probablePitcher,team,venue",
    })
    rows: list[dict[str, Any]] = []
    for day in payload.get("dates", []):
        for game in day.get("games", []):
            if game.get("status", {}).get("abstractGameState") != "Final":
                continue
            rows.append(game)
    return rows


def _actual_starting_pitchers(api: StatsApi, game_pk: int) -> dict[int, dict[str, Any]]:
    payload = api.get(f"game/{game_pk}/boxscore", {})
    result: dict[int, dict[str, Any]] = {}
    for side in ("away", "home"):
        team = payload.get("teams", {}).get(side, {})
        for player in team.get("players", {}).values():
            person = player.get("person", {})
            stats = player.get("stats", {}).get("pitching", {})
            if not stats or not stats.get("gamesStarted"):
                continue
            pid = int(person.get("id", 0))
            if pid:
                result[pid] = {
                    "name": person.get("fullName", "Unknown"),
                    "strikeouts": int(stats.get("strikeOuts", 0) or 0),
                    "batters_faced": int(stats.get("battersFaced", 0) or 0),
                    "team": team.get("team", {}).get("abbreviation", "UNK"),
                }
    return result


def _historical_pitcher_features(api: StatsApi, pitcher_id: int, season: int, game_date: str) -> dict[str, float]:
    payload = api.get(f"people/{pitcher_id}/stats", {
        "stats": "gameLog",
        "group": "pitching",
        "season": season,
        "gameType": "R",
    })
    rows: list[dict[str, float]] = []
    for block in payload.get("stats", []):
        for split in block.get("splits", []):
            if str(split.get("date", "")) >= game_date:
                continue
            stat = split.get("stat", {})
            bf = float(stat.get("battersFaced", 0) or 0)
            k = float(stat.get("strikeOuts", 0) or 0)
            if bf <= 0:
                continue
            rows.append({
                "bf": bf,
                "k": k,
                "k_rate": k / bf,
                "pitches": float(stat.get("numberOfPitches", 0) or 0),
                "outs": float(str(stat.get("inningsPitched", "0")).split(".")[0]) * 3
                + float(str(stat.get("inningsPitched", "0")).split(".")[1] or 0),
            })
    if not rows:
        return {
            "pitcher_k_pct": 0.224,
            "expected_bf": 23.0,
            "bf_sd": 3.5,
            "historical_k_sd": 2.0,
            "historical_games": 0,
            "prior_bf": 0.0,
        }

    frame = pd.DataFrame(rows).tail(35)
    weights = np.power(0.5, np.arange(len(frame) - 1, -1, -1) / 5.0)
    return {
        "pitcher_k_pct": float(np.average(frame["k_rate"], weights=weights)),
        "expected_bf": float(np.average(frame["bf"], weights=weights)),
        "bf_sd": float(max(frame["bf"].std(ddof=1), 1.0)) if len(frame) > 1 else 3.5,
        "historical_k_sd": float(max(frame["k"].std(ddof=1), 0.75)) if len(frame) > 1 else 2.0,
        "historical_games": int(len(frame)),
        "prior_bf": float(frame["bf"].sum()),
    }


def reconstruct_season(cfg: ReconstructionConfig) -> list[PregameSnapshot]:
    """Reconstruct only games where probable pitcher identity matches actual starter.

    The actual box score is used solely to resolve the target outcome. All
    pitcher features are rebuilt from games strictly before the target date.
    Historical lineup, weather and umpire snapshots are intentionally marked
    unavailable here rather than backfilled with postgame information.
    """
    api = StatsApi(cfg.timeout)
    snapshots: list[PregameSnapshot] = []
    for game in _game_rows(api, cfg):
        game_pk = int(game.get("gamePk", 0))
        game_date = str(game.get("officialDate", ""))
        actual = _actual_starting_pitchers(api, game_pk)
        if not actual:
            continue

        teams = game.get("teams", {})
        for side, opponent_side in (("away", "home"), ("home", "away")):
            probable = teams.get(side, {}).get("probablePitcher") or {}
            pid = int(probable.get("id", 0) or 0)
            if pid not in actual:
                # Fails closed: we cannot prove this pitcher was the announced
                # pregame starter from the schedule payload.
                continue
            outcome = actual[pid]
            try:
                features = _historical_pitcher_features(api, pid, cfg.season, game_date)
            except (requests.RequestException, ValueError, KeyError):
                continue

            features.update({
                "opponent_k_pct": 0.224,
                "handedness_factor": 1.0,
                "arsenal_factor": 1.0,
                "park_factor": 1.0,
                "umpire_factor": 1.0,
                "weather_factor": 1.0,
                "rest_factor": 1.0,
                "lineup_data_available": 0,
                "weather_data_available": 0,
                "umpire_data_available": 0,
                "historical_reconstruction": 1,
            })
            snapshots.append(make_snapshot(
                game_id=str(game_pk),
                game_date=game_date,
                pitcher_id=str(pid),
                pitcher_name=str(probable.get("fullName") or outcome["name"]),
                opponent_team=str(teams.get(opponent_side, {}).get("team", {}).get("abbreviation", "UNK")),
                features=features,
                source_versions={
                    "schedule": "MLB Stats API schedule",
                    "pitcher_history": "MLB Stats API gameLog",
                    "outcome": "MLB Stats API boxscore",
                },
                actual_strikeouts=outcome["strikeouts"],
                actual_batters_faced=outcome["batters_faced"],
            ))
    return snapshots
