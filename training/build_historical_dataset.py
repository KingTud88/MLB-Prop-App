from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from .baseball_features import build_baseball_features
from .snapshot_schema import make_snapshot, snapshots_to_frame

BASE = "https://statsapi.mlb.com/api/v1"


def get_json(path: str, params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(f"{BASE}/{path.lstrip('/')}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def previous_pitcher_games(pitcher_id: int, before: str, limit: int = 10) -> list[dict[str, Any]]:
    data = get_json(f"people/{pitcher_id}/stats", {
        "stats": "gameLog",
        "group": "pitching",
        "season": before[:4],
    })
    splits = data.get("stats", [{}])[0].get("splits", [])
    rows = [s for s in splits if s.get("date", "") < before]
    rows.sort(key=lambda x: x.get("date", ""), reverse=True)
    return rows[:limit]


def player_hand(pitcher_id: int) -> str:
    data = get_json(f"people/{pitcher_id}", {})
    people = data.get("people", [])
    return str(people[0].get("pitchHand", {}).get("code", "")) if people else ""


def team_hitting_log(team_id: int, before: str) -> list[dict[str, Any]]:
    data = get_json(f"teams/{team_id}/stats", {
        "stats": "gameLog",
        "group": "hitting",
        "season": before[:4],
    })
    splits = data.get("stats", [{}])[0].get("splits", [])
    rows = [s for s in splits if s.get("date", "") < before]
    rows.sort(key=lambda x: x.get("date", ""), reverse=True)
    return rows[-10:]


def opponent_features(team_id: int, before: str) -> tuple[float, float]:
    logs = team_hitting_log(team_id, before)
    if not logs:
        return 0.0, 0.0
    total_k = sum(float(x.get("stat", {}).get("strikeOuts", 0)) for x in logs)
    total_ab = sum(float(x.get("stat", {}).get("atBats", 0)) for x in logs)
    return (total_k / total_ab if total_ab else 0.0), float(len(logs))


def build_features(pitcher_id: int, opponent_team_id: int, game_date: str) -> dict[str, float]:
    logs = previous_pitcher_games(pitcher_id, game_date)
    hand = player_hand(pitcher_id)
    opponent_k_rate, opponent_games = opponent_features(opponent_team_id, game_date)

    rest = 5.0
    if logs:
        last_date = logs[0].get("date")
        if last_date:
            try:
                rest = max(0.0, (date.fromisoformat(game_date) - date.fromisoformat(last_date)).days)
            except ValueError:
                pass

    features = build_baseball_features(
        pitcher_logs=[x.get("stat", {}) for x in logs],
        pitcher_hand=hand,
        recent_days_rest=rest,
    )
    features["opponent_k_rate"] = opponent_k_rate
    features["opponent_prior_games"] = opponent_games
    return features


def game_snapshots(game_date: str) -> list[Any]:
    schedule = get_json("schedule", {"sportId": 1, "date": game_date, "hydrate": "probablePitcher,teams"})
    snapshots = []
    for day in schedule.get("dates", []):
        for game in day.get("games", []):
            if game.get("status", {}).get("abstractGameState") != "Final":
                continue
            game_id = str(game.get("gamePk"))
            for side in ("away", "home"):
                team = game.get("teams", {}).get(side, {})
                probable = team.get("probablePitcher") or {}
                pid = probable.get("id")
                if not pid:
                    continue
                opponent_side = "home" if side == "away" else "away"
                opponent = game.get("teams", {}).get(opponent_side, {})
                opponent_team = opponent.get("team", {})
                opponent_id = opponent_team.get("id")
                if not opponent_id:
                    continue
                try:
                    boxscore = get_json(f"game/{game_id}/boxscore", {})
                    players = boxscore.get("teams", {}).get(side, {}).get("players", {})
                    player = players.get(f"ID{pid}", {})
                    pitching = player.get("stats", {}).get("pitching", {})
                    ks = pitching.get("strikeOuts")
                    bf = pitching.get("battersFaced")
                    if ks is None:
                        continue
                except requests.RequestException:
                    continue

                features = build_features(int(pid), int(opponent_id), game_date)
                snapshots.append(make_snapshot(
                    game_id=game_id,
                    game_date=game_date,
                    pitcher_id=str(pid),
                    pitcher_name=probable.get("fullName", "Unknown"),
                    opponent_team=opponent_team.get("abbreviation", ""),
                    features=features,
                    source_versions={"mlb_stats_api": "v1", "reconstruction": "2.1.0"},
                    actual_strikeouts=int(ks),
                    actual_batters_faced=int(bf) if bf is not None else None,
                ))
    return snapshots


def main() -> None:
    parser = argparse.ArgumentParser(description="Build frozen pregame MLB pitcher snapshots.")
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--output", type=Path, default=Path("data/historical_snapshots.csv"))
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if end < start:
        raise SystemExit("end must be on or after start")

    snapshots = []
    current = start
    while current <= end:
        day = current.isoformat()
        try:
            snapshots.extend(game_snapshots(day))
            print(json.dumps({"date": day, "snapshots": len(snapshots)}), flush=True)
        except requests.RequestException as exc:
            print(json.dumps({"date": day, "error": str(exc)}), flush=True)
        current += timedelta(days=1)

    frame = snapshots_to_frame(snapshots)
    if frame.empty:
        raise SystemExit("No resolved pitcher snapshots were collected")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    print(json.dumps({"output": str(args.output), "rows": len(frame)}))


if __name__ == "__main__":
    main()
