from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

from .baseball_features import build_baseball_features
from .matchup_features import build_matchup_features
from .pitch_mix_matchup import build_pitch_mix_matchup_features
from .snapshot_schema import make_snapshot, snapshots_to_frame

BASE = "https://statsapi.mlb.com/api/v1"
SESSION = requests.Session()
CACHE: dict[tuple[str, str], dict[str, Any]] = {}


def get_json(path: str, params: dict[str, Any]) -> dict[str, Any]:
    key = (path, json.dumps(params, sort_keys=True))
    if key in CACHE:
        return CACHE[key]
    response = SESSION.get(f"{BASE}/{path.lstrip('/')}", params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    CACHE[key] = data
    return data


def previous_pitcher_games(pitcher_id: int, before: str, limit: int = 10) -> list[dict[str, Any]]:
    data = get_json(f"people/{pitcher_id}/stats", {"stats": "gameLog", "group": "pitching", "season": before[:4]})
    stats = data.get("stats") or []
    splits = stats[0].get("splits", []) if stats else []
    rows = [s for s in splits if s.get("date", "") < before]
    rows.sort(key=lambda x: x.get("date", ""), reverse=True)
    return rows[:limit]


def person_info(player_id: int) -> dict[str, Any]:
    data = get_json(f"people/{player_id}", {})
    people = data.get("people") or []
    return people[0] if people else {}


def player_hand(player_id: int) -> str:
    return str(person_info(player_id).get("pitchHand", {}).get("code", ""))


def historical_batter_k_rate(player_id: int, before: str) -> float:
    data = get_json(f"people/{player_id}/stats", {"stats": "gameLog", "group": "hitting", "season": before[:4]})
    stats = data.get("stats") or []
    if not stats:
        return 0.0
    splits = stats[0].get("splits", [])
    rows = [s for s in splits if s.get("date", "") < before][-10:]
    ks = sum(float(x.get("stat", {}).get("strikeOuts", 0)) for x in rows)
    ab = sum(float(x.get("stat", {}).get("atBats", 0)) for x in rows)
    return ks / ab if ab else 0.0


def historical_pitch_mix(pitcher_id: int, before: str) -> list[dict[str, Any]]:
    """Return pitch-mix aggregates from games before the target date when available."""
    data = get_json(f"people/{pitcher_id}/stats", {
        "stats": "gameLog", "group": "pitching", "season": before[:4]
    })
    stats = data.get("stats") or []
    if not stats:
        return []
    rows = [s for s in stats[0].get("splits", []) if s.get("date", "") < before][-10:]
    # MLB gameLog does not expose pitch-type metrics consistently. Keep this
    # neutral unless a richer historical pitch source is present in the row.
    mix: list[dict[str, Any]] = []
    for row in rows:
        stat = row.get("stat", {})
        for item in stat.get("pitchMix", []) if isinstance(stat.get("pitchMix"), list) else []:
            mix.append(item)
    return mix


def build_features(pitcher_id: int, opponent_team_id: int, game_date: str, opponent_players: list[dict[str, Any]]) -> dict[str, float]:
    logs = previous_pitcher_games(pitcher_id, game_date)
    hand = player_hand(pitcher_id)
    rest = 5.0
    if logs and logs[0].get("date"):
        try:
            rest = max(0.0, (date.fromisoformat(game_date) - date.fromisoformat(logs[0]["date"])).days)
        except ValueError:
            pass

    batters: list[dict[str, Any]] = []
    for player in opponent_players:
        pid = player.get("person", {}).get("id")
        if not pid:
            continue
        try:
            info = person_info(int(pid))
            bat_hand = str(info.get("batSide", {}).get("code", ""))
            k_rate = historical_batter_k_rate(int(pid), game_date)
        except requests.RequestException:
            continue
        batters.append({
            "hand": bat_hand,
            "strikeout_rate": k_rate,
            "strikeout_rate_same_hand": k_rate if bat_hand == hand else 0.0,
            "strikeout_rate_opposite_hand": k_rate if bat_hand != hand else 0.0,
        })

    arsenal = historical_pitch_mix(pitcher_id, game_date)
    features = build_baseball_features(
        pitcher_logs=[x.get("stat", {}) for x in logs],
        pitcher_hand=hand,
        recent_days_rest=rest,
        arsenal=arsenal,
    )
    features.update(build_matchup_features(hand, batters))
    features.update(build_pitch_mix_matchup_features(hand, arsenal, batters))
    features["opponent_team_id"] = float(opponent_team_id)
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
                    players = boxscore.get("teams", {}).get(opponent_side, {}).get("players", {})
                    opponent_players = list(players.values())
                    pitcher_players = boxscore.get("teams", {}).get(side, {}).get("players", {})
                    player = pitcher_players.get(f"ID{pid}", {})
                    pitching = player.get("stats", {}).get("pitching", {})
                    ks = pitching.get("strikeOuts")
                    bf = pitching.get("battersFaced")
                    if ks is None:
                        continue
                except requests.RequestException:
                    continue

                features = build_features(int(pid), int(opponent_id), game_date, opponent_players)
                snapshots.append(make_snapshot(
                    game_id=game_id,
                    game_date=game_date,
                    pitcher_id=str(pid),
                    pitcher_name=probable.get("fullName", "Unknown"),
                    opponent_team=opponent_team.get("abbreviation", ""),
                    features=features,
                    source_versions={"mlb_stats_api": "v1", "reconstruction": "2.3.0"},
                    actual_strikeouts=int(ks),
                    actual_batters_faced=int(bf) if bf is not None else None,
                ))
    return snapshots


def main() -> None:
    parser = argparse.ArgumentParser(description="Build frozen pregame MLB pitcher snapshots.")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
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
            print(json.dumps({"date": day, "snapshots": len(snapshots), "cache_entries": len(CACHE)}), flush=True)
        except requests.RequestException as exc:
            print(json.dumps({"date": day, "error": str(exc)}), flush=True)
        current += timedelta(days=1)

    frame = snapshots_to_frame(snapshots)
    if frame.empty:
        raise SystemExit("No resolved pitcher snapshots were collected")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    print(json.dumps({"output": str(args.output), "rows": len(frame), "cache_entries": len(CACHE)}))


if __name__ == "__main__":
    main()
