from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE = "https://statsapi.mlb.com/api/v1"
ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "data" / "projection_log.csv"
SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json", "User-Agent": "StrikeOutKing9000/3.2.0"})


def get_json(endpoint: str) -> dict:
    response = SESSION.get(f"{BASE}/{endpoint}", timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Unexpected MLB response")
    return data


def is_missing(value: object) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() == ""


def resolve_row(row: pd.Series) -> tuple[int | None, str | None]:
    if not is_missing(row.get("actual_strikeouts")):
        return int(float(row["actual_strikeouts"])), str(row.get("resolved_at_utc") or "")
    if is_missing(row.get("game_pk")) or is_missing(row.get("pitcher_id")):
        return None, None

    try:
        data = get_json(f"game/{int(float(row['game_pk']))}/boxscore")
        status = data.get("gameData", {}).get("status", {})
        if status.get("abstractGameState") != "Final":
            return None, None

        player_id = f"ID{int(float(row['pitcher_id']))}"
        player = data.get("teams", {}).get("away", {}).get("players", {}).get(player_id)
        if not player:
            player = data.get("teams", {}).get("home", {}).get("players", {}).get(player_id)
        strikeouts = (player or {}).get("stats", {}).get("pitching", {}).get("strikeOuts")
        if strikeouts is None:
            return None, None
        return int(strikeouts), datetime.now(timezone.utc).isoformat()
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return None, None


def main() -> None:
    if not LOG_PATH.exists():
        print("projection log does not exist; nothing to resolve")
        return

    frame = pd.read_csv(LOG_PATH)
    if frame.empty:
        print("projection log is empty; nothing to resolve")
        return

    resolved = 0
    for idx in frame.index:
        actual, timestamp = resolve_row(frame.loc[idx])
        if actual is not None:
            frame.at[idx, "actual_strikeouts"] = actual
            frame.at[idx, "resolved_at_utc"] = timestamp
            resolved += 1

    frame.to_csv(LOG_PATH, index=False)
    print(f"resolved {resolved} completed pitcher projections; rows={len(frame)}")


if __name__ == "__main__":
    main()
