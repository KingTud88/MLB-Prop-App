from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from automation.daily_projection_runner import pitcher_hand
from engine.lineup_context import LINEUP_ACTIVE_ROSTER, LINEUP_CONFIRMED, get_confirmed_lineup
from engine.opposing_batters import get_opposing_batters

VERSION = "handedness-matchup-context-v1"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"

COLUMNS = [
    "game_date", "game_pk", "pitcher_id", "player", "team", "opponent",
    "opponent_team_id", "game_time", "projection_captured_at_utc",
    "hand_context_captured_at_utc", "pitcher_hand", "lineup_source",
    "lineup_confirmed", "lineup_hash", "lineup_batters", "batter_left",
    "batter_right", "batter_switch", "batter_unknown", "same_hand_batters",
    "opposite_hand_batters", "opposite_hand_share", "split_available_batters",
    "split_unavailable_batters", "split_coverage", "matchup_pa", "opponent_k_pct",
    "lineage", "audit_eligible", "reason", "report_only",
    "production_authority", "capture_version",
]


def _num(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _utc(value: object) -> pd.Timestamp:
    return pd.to_datetime(value, errors="coerce", utc=True)


def _saved_context_key(row: pd.Series) -> tuple[int, int, str, str] | None:
    game_pk = _num(row.get("game_pk"))
    pitcher_id = _num(row.get("pitcher_id"))
    if game_pk is None or pitcher_id is None:
        return None
    return (
        int(game_pk), int(pitcher_id),
        str(row.get("lineup_source", LINEUP_ACTIVE_ROSTER) or LINEUP_ACTIVE_ROSTER),
        str(row.get("lineup_hash", "") or ""),
    )


def _hand_counts(hand: str, batters: pd.DataFrame) -> dict[str, object]:
    if batters is None or batters.empty:
        return {
            "lineup_batters": 0, "batter_left": 0, "batter_right": 0,
            "batter_switch": 0, "batter_unknown": 0, "same_hand_batters": 0,
            "opposite_hand_batters": 0, "opposite_hand_share": np.nan,
            "split_available_batters": 0, "split_unavailable_batters": 0,
            "split_coverage": np.nan,
        }
    sides = batters.get("Hand", pd.Series("", index=batters.index)).fillna("").astype(str).str.upper()
    left = int(sides.eq("L").sum())
    right = int(sides.eq("R").sum())
    switch = int(sides.eq("S").sum())
    unknown = int(len(batters) - left - right - switch)
    if hand == "R":
        same, opposite = right, left + switch
    elif hand == "L":
        same, opposite = left, right + switch
    else:
        same = opposite = 0
    split = batters.get("Split Available", pd.Series(False, index=batters.index))
    if not pd.api.types.is_bool_dtype(split):
        split = split.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})
    available = int(split.fillna(False).astype(bool).sum())
    total = int(len(batters))
    return {
        "lineup_batters": total,
        "batter_left": left,
        "batter_right": right,
        "batter_switch": switch,
        "batter_unknown": unknown,
        "same_hand_batters": same,
        "opposite_hand_batters": opposite,
        "opposite_hand_share": float(opposite / total) if total else np.nan,
        "split_available_batters": available,
        "split_unavailable_batters": total - available,
        "split_coverage": float(available / total) if total else np.nan,
    }


def build_capture_records(
    projections: pd.DataFrame,
    existing: pd.DataFrame | None = None,
    *,
    captured_at: pd.Timestamp | None = None,
    hand_resolver: Callable[[int], str] = pitcher_hand,
    lineup_resolver: Callable[..., object] = get_confirmed_lineup,
    batters_resolver: Callable[..., pd.DataFrame] = get_opposing_batters,
) -> pd.DataFrame:
    existing = existing.copy() if existing is not None else pd.DataFrame(columns=COLUMNS)
    if projections is None or projections.empty:
        return existing.reindex(columns=COLUMNS)
    now = captured_at if captured_at is not None else pd.Timestamp.now(tz="UTC")
    now = pd.to_datetime(now, utc=True)

    existing_keys: set[tuple[int, int, str, str]] = set()
    if not existing.empty:
        for _, row in existing.iterrows():
            key = _saved_context_key(row)
            if key is not None:
                existing_keys.add(key)

    additions: list[dict[str, object]] = []
    for _, row in projections.iterrows():
        key = _saved_context_key(row)
        if key is None or key in existing_keys:
            continue
        game_time = _utc(row.get("game_time"))
        if pd.isna(game_time) or game_time <= now:
            continue
        game_pk, pitcher_id, saved_source, saved_hash = key
        opponent_team_id = _num(row.get("opponent_team_id"))
        hand = str(hand_resolver(pitcher_id) or "").upper()
        confirmed_saved = _truthy(row.get("lineup_confirmed")) or saved_source == LINEUP_CONFIRMED
        batter_ids: tuple[int, ...] = ()
        lineup_spots: tuple[tuple[int, int], ...] = ()
        lineage = "PRE_GAME_ACTIVE_ROSTER"
        eligible = hand in {"R", "L"}
        reason = ""

        if confirmed_saved:
            ctx = lineup_resolver(game_pk, int(opponent_team_id or 0))
            current_confirmed = bool(getattr(ctx, "confirmed", False))
            current_hash = str(getattr(ctx, "fingerprint", "") or "")
            if not current_confirmed:
                lineage = "CONFIRMED_LINEUP_NOT_REPRODUCIBLE"
                eligible = False
                reason = "Saved confirmed lineup could not be reproduced at handedness capture."
            elif saved_hash and current_hash != saved_hash:
                lineage = "CONFIRMED_LINEUP_HASH_MISMATCH"
                eligible = False
                reason = "Current confirmed lineup fingerprint differs from the projection snapshot."
            else:
                lineage = "PRE_GAME_CONFIRMED_MATCH"
                batter_ids = tuple(int(x) for x in getattr(ctx, "player_ids", ()) if x)
                lineup_spots = tuple(getattr(ctx, "spots", ()) or ())
        if hand not in {"R", "L"}:
            eligible = False
            reason = reason or "Pitcher hand unavailable."

        batters = pd.DataFrame()
        if eligible and opponent_team_id is not None:
            season = int(pd.to_datetime(row.get("game_date"), errors="coerce").year)
            if season > 0:
                batters = batters_resolver(
                    str(row.get("opponent", "")), hand, season, int(opponent_team_id),
                    batter_ids, lineup_spots,
                )
        counts = _hand_counts(hand, batters)
        if counts["lineup_batters"] == 0:
            eligible = False
            reason = reason or "No batter split context available."

        additions.append({
            "game_date": str(row.get("game_date", "")),
            "game_pk": game_pk,
            "pitcher_id": pitcher_id,
            "player": str(row.get("player", "")),
            "team": str(row.get("team", "")),
            "opponent": str(row.get("opponent", "")),
            "opponent_team_id": np.nan if opponent_team_id is None else int(opponent_team_id),
            "game_time": game_time.isoformat(),
            "projection_captured_at_utc": str(row.get("captured_at_utc", "") or ""),
            "hand_context_captured_at_utc": now.isoformat(),
            "pitcher_hand": hand,
            "lineup_source": saved_source,
            "lineup_confirmed": confirmed_saved,
            "lineup_hash": saved_hash,
            **counts,
            "matchup_pa": _num(row.get("matchup_pa")) or 0,
            "opponent_k_pct": _num(row.get("opponent_k_pct")),
            "lineage": lineage,
            "audit_eligible": eligible,
            "reason": reason,
            "report_only": REPORT_ONLY,
            "production_authority": PRODUCTION_AUTHORITY,
            "capture_version": VERSION,
        })
        existing_keys.add(key)

    if additions:
        existing = pd.concat([existing, pd.DataFrame(additions)], ignore_index=True)
    for column in COLUMNS:
        if column not in existing.columns:
            existing[column] = np.nan
    return existing[COLUMNS].copy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture report-only pregame handedness matchup context.")
    parser.add_argument("--projection-log", default="data/projection_log.csv")
    parser.add_argument("--output", default="data/handedness_matchup_context_log.csv")
    args = parser.parse_args()
    projection_path = Path(args.projection_log)
    output_path = Path(args.output)
    projections = pd.read_csv(projection_path) if projection_path.exists() else pd.DataFrame()
    existing = pd.read_csv(output_path) if output_path.exists() else pd.DataFrame(columns=COLUMNS)
    result = build_capture_records(projections, existing)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    print(f"handedness_context_rows={len(result)} report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY}")


if __name__ == "__main__":
    main()
