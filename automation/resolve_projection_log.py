from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

BASE = "https://statsapi.mlb.com/api/v1"
ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "data" / "projection_log.csv"
SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json", "User-Agent": "StrikeOutKing9000/3.2.0"})


def get_json(endpoint: str, params: dict | None = None) -> dict:
    response = SESSION.get(f"{BASE}/{endpoint}", params=params or {}, timeout=30)
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


def resolve_from_pitcher_game_log(row: pd.Series) -> int | None:
    pitcher_id = int(float(row["pitcher_id"]))
    game_date = str(row["game_date"])[:10]
    season = game_date[:4]
    data = get_json(
        f"people/{pitcher_id}/stats",
        {"stats": "gameLog", "group": "pitching", "season": season, "gameType": "R"},
    )
    for block in data.get("stats", []):
        for split in block.get("splits", []):
            if str(split.get("date", ""))[:10] != game_date:
                continue
            stat = split.get("stat", {})
            strikeouts = stat.get("strikeOuts")
            if strikeouts is not None:
                return int(strikeouts)
    return None


def _pitcher_from_boxscore(data: dict, player_id: str) -> int | None:
    for side in ("away", "home"):
        player = data.get("teams", {}).get(side, {}).get("players", {}).get(player_id)
        strikeouts = (player or {}).get("stats", {}).get("pitching", {}).get("strikeOuts")
        if strikeouts is not None:
            return int(strikeouts)
    return None


def resolve_row(row: pd.Series) -> tuple[int | None, str | None, str | None]:
    if not is_missing(row.get("actual_strikeouts")):
        return int(float(row["actual_strikeouts"])), str(row.get("resolved_at_utc") or ""), None
    if is_missing(row.get("game_pk")) or is_missing(row.get("pitcher_id")):
        return None, None, "missing game/pitcher id"

    game_pk = int(float(row["game_pk"]))
    player_id = f"ID{int(float(row['pitcher_id']))}"
    try:
        # Primary source: the same official MLB pitcher game-log endpoint used
        # by the projection engine. This avoids relying on a boxscore transition.
        strikeouts = resolve_from_pitcher_game_log(row)
        if strikeouts is not None:
            return strikeouts, datetime.now(timezone.utc).isoformat(), None

        # Secondary official path for unusual game-log cases/doubleheaders.
        boxscore = get_json(f"game/{game_pk}/boxscore")
        status = boxscore.get("gameData", {}).get("status", {})
        if status.get("abstractGameState") == "Final":
            strikeouts = _pitcher_from_boxscore(boxscore, player_id)
            if strikeouts is not None:
                return strikeouts, datetime.now(timezone.utc).isoformat(), None
            return None, None, "final game but pitcher was not found in boxscore"

        live = get_json(f"game/{game_pk}/feed/live")
        live_status = live.get("gameData", {}).get("status", {})
        if live_status.get("abstractGameState") != "Final":
            return None, None, f"game not final ({live_status.get('abstractGameState', 'unknown')})"
        live_boxscore = live.get("liveData", {}).get("boxscore", {})
        strikeouts = _pitcher_from_boxscore(live_boxscore, player_id)
        if strikeouts is None:
            return None, None, "final live feed but pitcher was not found"
        return strikeouts, datetime.now(timezone.utc).isoformat(), None
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        return None, None, f"MLB API error: {type(exc).__name__}"


def main() -> None:
    if not LOG_PATH.exists():
        print("projection log does not exist; nothing to resolve")
        return

    frame = pd.read_csv(LOG_PATH)
    if frame.empty:
        print("projection log is empty; nothing to resolve")
        return

    resolved = 0
    unresolved_reasons: dict[str, int] = {}
    for idx in frame.index:
        actual, timestamp, reason = resolve_row(frame.loc[idx])
        if actual is not None:
            frame.at[idx, "actual_strikeouts"] = actual
            frame.at[idx, "resolved_at_utc"] = timestamp
            resolved += 1
        elif reason:
            unresolved_reasons[reason] = unresolved_reasons.get(reason, 0) + 1

    frame.to_csv(LOG_PATH, index=False)
    print(f"resolved {resolved} completed pitcher projections; rows={len(frame)}")
    if unresolved_reasons:
        print(f"unresolved reasons: {unresolved_reasons}")


if __name__ == "__main__":
    main()
