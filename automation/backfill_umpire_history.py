from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta

import pandas as pd

from automation.daily_projection_runner import get_json
from engine.umpire_context import OBS_PATH, load_observations, resolved_game_observation, save_observations


def _game_rows(start_date: str, end_date: str) -> list[tuple[int, str]]:
    data = get_json(
        "schedule",
        {"sportId": 1, "gameType": "R", "startDate": start_date, "endDate": end_date},
    )
    rows: list[tuple[int, str]] = []
    for day in data.get("dates", []):
        game_date = str(day.get("date") or "")
        for game in day.get("games", []):
            game_pk = game.get("gamePk")
            if game_pk is not None:
                rows.append((int(game_pk), game_date))
    return rows


def backfill(start_date: str, end_date: str) -> tuple[pd.DataFrame, int, int]:
    observations = load_observations(OBS_PATH)
    known = set(pd.to_numeric(observations.get("game_pk", pd.Series(dtype=float)), errors="coerce").dropna().astype(int))
    added = 0
    attempted = 0
    for game_pk, game_date in _game_rows(start_date, end_date):
        if game_pk in known:
            continue
        attempted += 1
        try:
            feed = get_json(f"game/{game_pk}/feed/live", {})
            record = resolved_game_observation(feed, game_pk, game_date)
        except Exception as exc:
            print(f"umpire backfill skipped game={game_pk}: {exc}")
            continue
        if not record:
            continue
        observations = pd.concat([observations, pd.DataFrame([record])], ignore_index=True)
        known.add(game_pk)
        added += 1
        if added % 100 == 0:
            print(f"umpire backfill progress added={added} attempted={attempted}")
    observations = observations.sort_values(["game_date", "game_pk"], kind="stable").reset_index(drop=True)
    return observations, attempted, added


def main() -> None:
    parser = argparse.ArgumentParser(description="One-time leakage-safe historical umpire observation backfill")
    parser.add_argument("--start-date", default="2026-03-25")
    parser.add_argument("--end-date", default=(date.today() - timedelta(days=1)).isoformat())
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start_date).date()
    end = datetime.fromisoformat(args.end_date).date()
    if end < start:
        raise SystemExit("end-date must be on or after start-date")
    observations, attempted, added = backfill(start.isoformat(), end.isoformat())
    save_observations(observations, OBS_PATH)
    umpire_counts = observations.groupby("umpire_id").size() if not observations.empty else pd.Series(dtype=int)
    mature = int((umpire_counts >= 20).sum())
    print(
        f"umpire_backfill_start={start} end={end} attempted={attempted} added={added} "
        f"total_observations={len(observations)} umpires_20p={mature}"
    )


if __name__ == "__main__":
    main()
