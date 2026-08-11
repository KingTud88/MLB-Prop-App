from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

BASE = "https://statsapi.mlb.com/api/v1"
ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "data" / "projection_log.csv"
SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json", "User-Agent": "StrikeOutKing9000/3.5.0"})


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


def parse_outs(innings_pitched: object) -> int | None:
    try:
        whole, frac = str(innings_pitched).split(".")
        frac_i = int(frac)
        if frac_i not in (0, 1, 2):
            return None
        return int(whole) * 3 + frac_i
    except (TypeError, ValueError):
        return None


def _pitcher_stats_from_boxscore(data: dict, player_id: str) -> tuple[int | None, int | None, int | None]:
    for side in ("away", "home"):
        player = data.get("teams", {}).get(side, {}).get("players", {}).get(player_id)
        pitching = (player or {}).get("stats", {}).get("pitching", {})
        if pitching:
            strikeouts = pitching.get("strikeOuts")
            hits = pitching.get("hits")
            outs = parse_outs(pitching.get("inningsPitched"))
            return (
                int(strikeouts) if strikeouts is not None else None,
                int(hits) if hits is not None else None,
                outs,
            )
    return None, None, None


def resolve_row(row: pd.Series) -> tuple[int | None, int | None, int | None, str | None, str | None]:
    have_k = not is_missing(row.get("actual_strikeouts"))
    have_hits = not is_missing(row.get("actual_hits_allowed"))
    have_outs = not is_missing(row.get("actual_outs"))
    if have_k and have_hits and have_outs:
        return (
            int(float(row["actual_strikeouts"])),
            int(float(row["actual_hits_allowed"])),
            int(float(row["actual_outs"])),
            str(row.get("resolved_at_utc") or ""),
            None,
        )
    if is_missing(row.get("game_pk")) or is_missing(row.get("pitcher_id")):
        return None, None, None, None, "missing game/pitcher id"

    game_pk = int(float(row["game_pk"]))
    player_id = f"ID{int(float(row['pitcher_id']))}"
    try:
        boxscore = get_json(f"game/{game_pk}/boxscore")
        status = boxscore.get("gameData", {}).get("status", {})
        if status.get("abstractGameState") != "Final":
            live = get_json(f"game/{game_pk}/feed/live")
            live_status = live.get("gameData", {}).get("status", {})
            if live_status.get("abstractGameState") != "Final":
                return None, None, None, None, f"game not final ({live_status.get('abstractGameState', 'unknown')})"
            boxscore = live.get("liveData", {}).get("boxscore", {})

        strikeouts, hits, outs = _pitcher_stats_from_boxscore(boxscore, player_id)
        if strikeouts is None and hits is None and outs is None:
            return None, None, None, None, "final game but pitcher was not found in boxscore"
        return strikeouts, hits, outs, datetime.now(timezone.utc).isoformat(), None
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        return None, None, None, None, f"MLB API error: {type(exc).__name__}"


def main() -> None:
    if not LOG_PATH.exists():
        print("projection log does not exist; nothing to resolve")
        return

    frame = pd.read_csv(LOG_PATH)
    if frame.empty:
        print("projection log is empty; nothing to resolve")
        return

    for col in ("actual_strikeouts", "actual_hits_allowed", "actual_outs"):
        if col not in frame.columns:
            frame[col] = pd.NA
    if "resolved_at_utc" not in frame.columns:
        frame["resolved_at_utc"] = ""
    else:
        frame["resolved_at_utc"] = frame["resolved_at_utc"].fillna("").astype(str)

    resolved = 0
    unresolved_reasons: dict[str, int] = {}
    for idx in frame.index:
        strikeouts, hits, outs, timestamp, reason = resolve_row(frame.loc[idx])
        changed = False
        if strikeouts is not None:
            frame.at[idx, "actual_strikeouts"] = strikeouts
            changed = True
        if hits is not None:
            frame.at[idx, "actual_hits_allowed"] = hits
            changed = True
        if outs is not None:
            frame.at[idx, "actual_outs"] = outs
            changed = True
        if changed:
            frame.at[idx, "resolved_at_utc"] = timestamp or ""
            resolved += 1
        elif reason:
            unresolved_reasons[reason] = unresolved_reasons.get(reason, 0) + 1

    frame.to_csv(LOG_PATH, index=False)
    print(f"resolved {resolved} completed pitcher projections; rows={len(frame)}")
    if unresolved_reasons:
        print(f"unresolved reasons: {unresolved_reasons}")


if __name__ == "__main__":
    main()
