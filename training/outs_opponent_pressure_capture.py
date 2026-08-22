from __future__ import annotations

import argparse
from datetime import timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import requests

from automation.daily_projection_runner import pitcher_hand
from engine.lineup_context import LINEUP_ACTIVE_ROSTER, LINEUP_CONFIRMED, get_confirmed_lineup

VERSION = "outs-opponent-pressure-context-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
FIRST_ELIGIBLE_GAME_DATE = "2026-08-23"
MLB_API = "https://statsapi.mlb.com/api/v1"
LEAGUE_K_RATE = 0.224
LEAGUE_OBP = 0.320
LINEUP_SPLIT_PRIOR_PA = 60.0
MIN_ROW_SPLIT_COVERAGE = 0.60

BATTER_COLUMNS = ["Batter", "PA", "K_Rate", "OBP", "Split_Available"]
COLUMNS = [
    "game_date", "game_pk", "pitcher_id", "player", "team", "opponent",
    "opponent_team_id", "game_time", "projection_captured_at_utc",
    "pressure_captured_at_utc", "pitcher_hand", "lineup_source",
    "lineup_confirmed", "lineup_hash", "lineup_batters",
    "split_available_batters", "split_unavailable_batters", "split_coverage",
    "matchup_pa", "opponent_k_rate", "opponent_contact_rate", "opponent_obp",
    "projection_opponent_k_pct", "projection_opponent_hit_rate",
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


def _obp_from_stat(stat: dict) -> float | None:
    direct = _num(stat.get("onBasePercentage"))
    if direct is not None:
        return float(np.clip(direct, 0.0, 1.0))
    hits = _num(stat.get("hits")) or 0.0
    walks = _num(stat.get("baseOnBalls")) or 0.0
    hbp = _num(stat.get("hitByPitch")) or 0.0
    at_bats = _num(stat.get("atBats")) or 0.0
    sac_flies = _num(stat.get("sacFlies")) or 0.0
    denominator = at_bats + walks + hbp + sac_flies
    if denominator <= 0:
        return None
    return float(np.clip((hits + walks + hbp) / denominator, 0.0, 1.0))


def fetch_pressure_batters(
    opponent_team_id: int,
    pitcher_hand_code: str,
    season: int,
    batter_ids: tuple[int, ...] = (),
    *,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    hand = str(pitcher_hand_code or "").upper()
    sit = "vr" if hand == "R" else "vl" if hand == "L" else None
    if not opponent_team_id or not sit:
        return pd.DataFrame(columns=BATTER_COLUMNS)

    client = session or requests.Session()
    client.headers.update({"Accept": "application/json", "User-Agent": "StrikeOutKing9000/research"})
    confirmed = tuple(int(x) for x in batter_ids if x)
    try:
        if confirmed:
            ids = list(dict.fromkeys(confirmed))
        else:
            roster = client.get(
                f"{MLB_API}/teams/{int(opponent_team_id)}/roster",
                params={"rosterType": "active", "season": int(season)},
                timeout=12,
            )
            roster.raise_for_status()
            ids = [
                int(item["person"]["id"])
                for item in roster.json().get("roster", [])
                if item.get("person", {}).get("id") and item.get("position", {}).get("code") != "1"
            ]

        rows: list[dict[str, object]] = []
        seen: set[int] = set()
        for start in range(0, len(ids), 20):
            batch = ids[start:start + 20]
            response = client.get(
                f"{MLB_API}/people",
                params={
                    "personIds": ",".join(map(str, batch)),
                    "hydrate": f"stats(group=hitting,type=statSplits,sitCodes={sit},season={int(season)})",
                },
                timeout=15,
            )
            response.raise_for_status()
            for person in response.json().get("people", []):
                pid = int(person.get("id"))
                best_pa = -1.0
                best_k: float | None = None
                best_obp: float | None = None
                for block in person.get("stats", []):
                    for split in block.get("splits", []):
                        stat = split.get("stat", {}) or {}
                        pa = _num(stat.get("plateAppearances")) or 0.0
                        if pa <= 0:
                            continue
                        strikeouts = _num(stat.get("strikeOuts")) or 0.0
                        obp = _obp_from_stat(stat)
                        if obp is None:
                            continue
                        if pa > best_pa:
                            best_pa = pa
                            best_k = float(np.clip(strikeouts / pa, 0.0, 1.0))
                            best_obp = obp
                if best_k is not None and best_obp is not None:
                    rows.append({
                        "Batter": str(person.get("fullName") or f"MLB ID {pid}"),
                        "PA": best_pa,
                        "K_Rate": best_k,
                        "OBP": best_obp,
                        "Split_Available": True,
                    })
                    seen.add(pid)
                elif confirmed:
                    rows.append({
                        "Batter": str(person.get("fullName") or f"MLB ID {pid}"),
                        "PA": 0.0,
                        "K_Rate": LEAGUE_K_RATE,
                        "OBP": LEAGUE_OBP,
                        "Split_Available": False,
                    })
                    seen.add(pid)
        if confirmed:
            for pid in confirmed:
                if pid not in seen:
                    rows.append({
                        "Batter": f"MLB ID {pid}", "PA": 0.0,
                        "K_Rate": LEAGUE_K_RATE, "OBP": LEAGUE_OBP,
                        "Split_Available": False,
                    })
        return pd.DataFrame(rows, columns=BATTER_COLUMNS)
    except (requests.RequestException, ValueError, TypeError):
        return pd.DataFrame(columns=BATTER_COLUMNS)


def summarize_pressure(batters: pd.DataFrame, *, confirmed_lineup: bool) -> dict[str, object]:
    if batters is None or batters.empty:
        return {
            "lineup_batters": 0, "split_available_batters": 0,
            "split_unavailable_batters": 0, "split_coverage": np.nan,
            "matchup_pa": 0.0, "opponent_k_rate": np.nan,
            "opponent_contact_rate": np.nan, "opponent_obp": np.nan,
        }
    pa = pd.to_numeric(batters["PA"], errors="coerce").fillna(0.0).clip(lower=0.0)
    k = pd.to_numeric(batters["K_Rate"], errors="coerce").fillna(LEAGUE_K_RATE).clip(0.0, 1.0)
    obp = pd.to_numeric(batters["OBP"], errors="coerce").fillna(LEAGUE_OBP).clip(0.0, 1.0)
    split = batters["Split_Available"].fillna(False).astype(bool)
    total = int(len(batters))
    available = int(split.sum())
    total_pa = float(pa.sum())
    if confirmed_lineup:
        adj_k = (k * pa + LEAGUE_K_RATE * LINEUP_SPLIT_PRIOR_PA) / (pa + LINEUP_SPLIT_PRIOR_PA)
        adj_obp = (obp * pa + LEAGUE_OBP * LINEUP_SPLIT_PRIOR_PA) / (pa + LINEUP_SPLIT_PRIOR_PA)
        k_rate = float(adj_k.mean())
        obp_rate = float(adj_obp.mean())
    elif total_pa > 0:
        k_rate = float((k * pa).sum() / total_pa)
        obp_rate = float((obp * pa).sum() / total_pa)
    else:
        k_rate = LEAGUE_K_RATE
        obp_rate = LEAGUE_OBP
    k_rate = float(np.clip(k_rate, 0.08, 0.45))
    obp_rate = float(np.clip(obp_rate, 0.20, 0.45))
    return {
        "lineup_batters": total,
        "split_available_batters": available,
        "split_unavailable_batters": total - available,
        "split_coverage": float(available / total) if total else np.nan,
        "matchup_pa": total_pa,
        "opponent_k_rate": k_rate,
        "opponent_contact_rate": float(1.0 - k_rate),
        "opponent_obp": obp_rate,
    }


def _saved_key(row: pd.Series) -> tuple[int, int, str, str] | None:
    game_pk = _num(row.get("game_pk"))
    pitcher_id = _num(row.get("pitcher_id"))
    if game_pk is None or pitcher_id is None:
        return None
    return (
        int(game_pk), int(pitcher_id),
        str(row.get("lineup_source", LINEUP_ACTIVE_ROSTER) or LINEUP_ACTIVE_ROSTER),
        str(row.get("lineup_hash", "") or ""),
    )


def build_capture_records(
    projections: pd.DataFrame,
    existing: pd.DataFrame | None = None,
    *,
    captured_at: pd.Timestamp | None = None,
    hand_resolver: Callable[[int], str] = pitcher_hand,
    lineup_resolver: Callable[..., object] = get_confirmed_lineup,
    batters_resolver: Callable[..., pd.DataFrame] = fetch_pressure_batters,
) -> pd.DataFrame:
    existing = existing.copy() if existing is not None else pd.DataFrame(columns=COLUMNS)
    if projections is None or projections.empty:
        return existing.reindex(columns=COLUMNS)
    now = pd.to_datetime(captured_at if captured_at is not None else pd.Timestamp.now(tz="UTC"), utc=True)
    existing_keys = {
        key for _, row in existing.iterrows()
        if (key := _saved_key(row)) is not None
    }
    additions: list[dict[str, object]] = []

    for _, row in projections.iterrows():
        game_date = pd.to_datetime(row.get("game_date"), errors="coerce")
        if pd.isna(game_date) or game_date < pd.Timestamp(FIRST_ELIGIBLE_GAME_DATE):
            continue
        key = _saved_key(row)
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
        lineage = "PRE_GAME_ACTIVE_ROSTER"
        eligible = hand in {"R", "L"} and opponent_team_id is not None
        reason = ""

        if confirmed_saved and eligible:
            ctx = lineup_resolver(game_pk, int(opponent_team_id or 0))
            current_confirmed = bool(getattr(ctx, "confirmed", False))
            current_hash = str(getattr(ctx, "fingerprint", "") or "")
            if not current_confirmed:
                lineage = "CONFIRMED_LINEUP_NOT_REPRODUCIBLE"
                eligible = False
                reason = "Saved confirmed lineup could not be reproduced at pressure capture."
            elif saved_hash and current_hash != saved_hash:
                lineage = "CONFIRMED_LINEUP_HASH_MISMATCH"
                eligible = False
                reason = "Current confirmed lineup fingerprint differs from the projection snapshot."
            else:
                lineage = "PRE_GAME_CONFIRMED_MATCH"
                batter_ids = tuple(int(x) for x in getattr(ctx, "player_ids", ()) if x)
        if hand not in {"R", "L"}:
            eligible = False
            reason = reason or "Pitcher hand unavailable."
        if opponent_team_id is None:
            eligible = False
            reason = reason or "Opponent team id unavailable."

        batters = pd.DataFrame(columns=BATTER_COLUMNS)
        if eligible:
            season = int(game_date.year)
            batters = batters_resolver(int(opponent_team_id), hand, season, batter_ids)
        summary = summarize_pressure(batters, confirmed_lineup=confirmed_saved)
        coverage = _num(summary.get("split_coverage"))
        if int(summary.get("lineup_batters", 0) or 0) == 0:
            eligible = False
            reason = reason or "No opponent split context available."
        elif coverage is None or coverage < MIN_ROW_SPLIT_COVERAGE:
            eligible = False
            reason = reason or f"Split coverage below frozen {MIN_ROW_SPLIT_COVERAGE:.0%} row minimum."

        additions.append({
            "game_date": game_date.date().isoformat(), "game_pk": game_pk,
            "pitcher_id": pitcher_id, "player": str(row.get("player", "")),
            "team": str(row.get("team", "")), "opponent": str(row.get("opponent", "")),
            "opponent_team_id": np.nan if opponent_team_id is None else int(opponent_team_id),
            "game_time": game_time.isoformat(),
            "projection_captured_at_utc": str(row.get("captured_at_utc", "") or ""),
            "pressure_captured_at_utc": now.isoformat(), "pitcher_hand": hand,
            "lineup_source": saved_source, "lineup_confirmed": confirmed_saved,
            "lineup_hash": saved_hash, **summary,
            "projection_opponent_k_pct": _num(row.get("opponent_k_pct")),
            "projection_opponent_hit_rate": _num(row.get("opponent_hit_rate")),
            "lineage": lineage, "audit_eligible": bool(eligible), "reason": reason,
            "report_only": REPORT_ONLY, "production_authority": PRODUCTION_AUTHORITY,
            "capture_version": VERSION,
        })
        existing_keys.add(key)

    if additions:
        added = pd.DataFrame(additions)
        existing = added if existing.empty else pd.concat([existing, added], ignore_index=True)
    for column in COLUMNS:
        if column not in existing.columns:
            existing[column] = np.nan
    return existing[COLUMNS].copy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture report-only pregame opponent pressure context for starter outs.")
    parser.add_argument("--projection-log", default="data/projection_log.csv")
    parser.add_argument("--output", default="data/outs_opponent_pressure_context_log.csv")
    args = parser.parse_args()
    projection_path = Path(args.projection_log)
    output_path = Path(args.output)
    projections = pd.read_csv(projection_path) if projection_path.exists() else pd.DataFrame()
    existing = pd.read_csv(output_path) if output_path.exists() else pd.DataFrame(columns=COLUMNS)
    result = build_capture_records(projections, existing)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    print(f"outs_pressure_context_rows={len(result)} report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY}")


if __name__ == "__main__":
    main()
