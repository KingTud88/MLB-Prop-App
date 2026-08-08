from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

from .snapshot_schema import make_snapshot, snapshots_to_frame

BASE = "https://statsapi.mlb.com/api/v1"


def get_json(path: str, params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(f"{BASE}/{path.lstrip('/')}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def previous_pitcher_games(pitcher_id: int, before: str, limit: int = 10) -> list[dict[str, Any]]:
    data = get_json("people/{}/stats".format(pitcher_id), {
        "stats": "gameLog",
        "group": "pitching",
        "season": before[:4],
    })
    splits = data.get("stats", [{}])[0].get("splits", [])
    rows = [s for s in splits if s.get("date", "") < before]
    rows.sort(key=lambda x: x.get("date", ""), reverse=True)
    return rows[:limit]


def build_features(pitcher_id: int, game_date: str) -> dict[str, float]:
    logs = previous_pitcher_games(pitcher_id, game_date)
    if not logs:
        return {"prior_games": 0.0, "prior_strikeouts": 0.0, "prior_ip": 0.0, "prior_k_per_9": 0.0}
    ks = sum(float(x.get("stat", {}).get("strikeOuts", 0)) for x in logs)
    ip = sum(float(x.get("stat", {}).get("inningsPitched", 0)) for x in logs)
    return {
        "prior_games": float(len(logs)),
        "prior_strikeouts": ks,
        "prior_ip": ip,
        "prior_k_per_9": (ks * 9.0 / ip) if ip else 0.0,
    }


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
                box = team.get("score")
                opponent = game.get("teams", {}).get("home" if side == "away" else "away", {}).get("team", {}).get("abbreviation", "")
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
                features = build_features(int(pid), game_date)
                snapshots.append(make_snapshot(
                    game_id=game_id,
                    game_date=game_date,
                    pitcher_id=str(pid),
                    pitcher_name=probable.get("fullName", "Unknown"),
                    opponent_team=opponent,
                    features=features,
                    source_versions={"mlb_stats_api": "v1", "reconstruction": "1.0.0"},
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
