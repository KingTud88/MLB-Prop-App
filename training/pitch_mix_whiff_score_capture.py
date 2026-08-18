from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

VERSION = "pitch-mix-whiff-score-v1-preregistered-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_PROJECTION_ADJUSTMENT = True
FORMULA_ID = "ARSENAL_USAGE_X_BATTER_WHIFF_V1"
MIN_BATTER_ARSENAL_USAGE_COVERAGE = 0.50
MIN_WEIGHTED_ARSENAL_USAGE_COVERAGE = 0.60
MIN_SCORE_BATTERS = 5

COLUMNS = [
    "game_date", "game_pk", "pitcher_id", "player", "team", "opponent",
    "lineup_source", "lineup_hash", "whiff_context_captured_at_utc",
    "arsenal_captured_at_utc", "score_batters", "requested_batters",
    "batter_weighting", "weighted_arsenal_usage_coverage", "pitch_mix_whiff_score",
    "baseline_whiff_rate", "pitch_mix_whiff_delta", "batter_scores_json",
    "formula_id", "formula_definition", "audit_eligible", "reason",
    "report_only", "production_authority", "no_projection_adjustment", "score_version",
]


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _clean(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _num(value: object) -> int | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else int(parsed)


def _key(row: pd.Series) -> tuple[int, int, str, str] | None:
    game_pk = _num(row.get("game_pk"))
    pitcher_id = _num(row.get("pitcher_id"))
    if game_pk is None or pitcher_id is None:
        return None
    return game_pk, pitcher_id, _clean(row.get("lineup_source")) or "ACTIVE_ROSTER", _clean(row.get("lineup_hash"))


def _eligible(frame: pd.DataFrame | None) -> pd.DataFrame:
    frame = frame.copy() if frame is not None else pd.DataFrame()
    if frame.empty or "audit_eligible" not in frame.columns:
        return frame
    return frame.loc[frame["audit_eligible"].map(_truthy)].copy()


def _loads_dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = _clean(value)
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalized_usage(value: object) -> dict[str, float]:
    raw = _loads_dict(value)
    usage: dict[str, float] = {}
    for pitch_type, amount in raw.items():
        try:
            number = max(0.0, float(amount))
        except (TypeError, ValueError):
            continue
        if number > 0:
            usage[str(pitch_type)] = number
    total = sum(usage.values())
    if total <= 0:
        return {}
    return {pitch_type: amount / total for pitch_type, amount in usage.items()}


def _batter_score(
    rates: dict[str, Any],
    counts: dict[str, Any],
    arsenal_usage: dict[str, float],
) -> dict[str, float] | None:
    rate_map: dict[str, float] = {}
    for pitch_type, value in rates.items():
        try:
            rate = float(value)
        except (TypeError, ValueError):
            continue
        if np.isfinite(rate) and 0.0 <= rate <= 1.0 and pitch_type in arsenal_usage:
            rate_map[str(pitch_type)] = rate
    coverage = float(sum(arsenal_usage[pitch_type] for pitch_type in rate_map))
    if coverage < MIN_BATTER_ARSENAL_USAGE_COVERAGE:
        return None

    expected = float(sum(arsenal_usage[pitch_type] * rate for pitch_type, rate in rate_map.items()) / coverage)
    total_swings = 0
    total_whiffs = 0
    for node in counts.values():
        if not isinstance(node, dict):
            continue
        try:
            swings = max(0, int(node.get("swings", 0)))
            whiffs = max(0, int(node.get("whiffs", 0)))
        except (TypeError, ValueError):
            continue
        total_swings += swings
        total_whiffs += min(swings, whiffs)
    if total_swings <= 0:
        return None
    baseline = float(total_whiffs / total_swings)
    return {
        "pitch_mix_whiff": expected,
        "baseline_whiff": baseline,
        "delta": expected - baseline,
        "arsenal_usage_coverage": coverage,
        "recent_swings": float(total_swings),
    }


def score_one_context(
    whiff_row: pd.Series,
    arsenal_row: pd.Series,
) -> dict[str, object]:
    arsenal_usage = _normalized_usage(arsenal_row.get("arsenal_usage"))
    rates_payload = _loads_dict(whiff_row.get("batter_pitch_whiff_rates_json"))
    counts_payload = _loads_dict(whiff_row.get("batter_pitch_counts_json"))
    requested = _num(whiff_row.get("batters_requested")) or len(rates_payload)
    confirmed = _clean(whiff_row.get("lineup_source")) == "CONFIRMED_LINEUP"
    weighting = "EQUAL_CONFIRMED_LINEUP" if confirmed else "RECENT_SWINGS_ACTIVE_ROSTER"

    batter_rows: dict[str, dict[str, float]] = {}
    for batter_id, rates in rates_payload.items():
        if not isinstance(rates, dict):
            continue
        counts = counts_payload.get(str(batter_id), {})
        if not isinstance(counts, dict):
            counts = {}
        score = _batter_score(rates, counts, arsenal_usage)
        if score is None:
            continue
        weight = 1.0 if confirmed else score["recent_swings"]
        if weight <= 0:
            continue
        batter_rows[str(batter_id)] = {**score, "weight": float(weight)}

    total_weight = sum(row["weight"] for row in batter_rows.values())
    if total_weight > 0:
        mix_score = sum(row["pitch_mix_whiff"] * row["weight"] for row in batter_rows.values()) / total_weight
        baseline = sum(row["baseline_whiff"] * row["weight"] for row in batter_rows.values()) / total_weight
        coverage = sum(row["arsenal_usage_coverage"] * row["weight"] for row in batter_rows.values()) / total_weight
    else:
        mix_score = baseline = coverage = np.nan
    delta = mix_score - baseline if np.isfinite(mix_score) and np.isfinite(baseline) else np.nan

    eligible = True
    reason = ""
    if not arsenal_usage:
        eligible = False
        reason = "Frozen pitcher arsenal usage unavailable."
    elif len(batter_rows) < MIN_SCORE_BATTERS:
        eligible = False
        reason = f"Only {len(batter_rows)} batters meet score coverage; need at least {MIN_SCORE_BATTERS}."
    elif not np.isfinite(coverage) or coverage < MIN_WEIGHTED_ARSENAL_USAGE_COVERAGE:
        eligible = False
        reason = (
            f"Weighted arsenal usage coverage {coverage!r} below "
            f"{MIN_WEIGHTED_ARSENAL_USAGE_COVERAGE:.2f}."
        )

    return {
        "game_date": _clean(whiff_row.get("game_date")),
        "game_pk": _num(whiff_row.get("game_pk")),
        "pitcher_id": _num(whiff_row.get("pitcher_id")),
        "player": _clean(whiff_row.get("player")),
        "team": _clean(whiff_row.get("team")),
        "opponent": _clean(whiff_row.get("opponent")),
        "lineup_source": _clean(whiff_row.get("lineup_source")) or "ACTIVE_ROSTER",
        "lineup_hash": _clean(whiff_row.get("lineup_hash")),
        "whiff_context_captured_at_utc": _clean(whiff_row.get("whiff_context_captured_at_utc")),
        "arsenal_captured_at_utc": _clean(arsenal_row.get("arsenal_captured_at_utc")),
        "score_batters": len(batter_rows),
        "requested_batters": requested,
        "batter_weighting": weighting,
        "weighted_arsenal_usage_coverage": coverage,
        "pitch_mix_whiff_score": mix_score,
        "baseline_whiff_rate": baseline,
        "pitch_mix_whiff_delta": delta,
        "batter_scores_json": json.dumps(batter_rows, sort_keys=True, separators=(",", ":")),
        "formula_id": FORMULA_ID,
        "formula_definition": (
            "For each batter, normalize pitcher usage across pitch types with >=5 frozen batter swings; "
            "compute usage-weighted Whiff%; compare with that batter's all-pitch prior-team-game Whiff%. "
            "Confirmed lineups weight batters equally; active-roster fallbacks weight by recent swings."
        ),
        "audit_eligible": eligible,
        "reason": reason,
        "report_only": REPORT_ONLY,
        "production_authority": PRODUCTION_AUTHORITY,
        "no_projection_adjustment": NO_PROJECTION_ADJUSTMENT,
        "score_version": VERSION,
    }


def build_score_frame(
    whiff_context: pd.DataFrame,
    arsenal_context: pd.DataFrame,
    hand_context: pd.DataFrame,
) -> pd.DataFrame:
    whiff = _eligible(whiff_context)
    arsenal = _eligible(arsenal_context)
    hand = _eligible(hand_context)
    if whiff.empty or arsenal.empty or hand.empty:
        return pd.DataFrame(columns=COLUMNS)

    current_keys = {key for _, row in hand.iterrows() if (key := _key(row)) is not None}
    arsenal_rows: dict[tuple[int, int], pd.Series] = {}
    for _, row in arsenal.iterrows():
        game_pk = _num(row.get("game_pk"))
        pitcher_id = _num(row.get("pitcher_id"))
        if game_pk is not None and pitcher_id is not None:
            arsenal_rows[(game_pk, pitcher_id)] = row

    rows: list[dict[str, object]] = []
    for _, whiff_row in whiff.iterrows():
        key = _key(whiff_row)
        if key is None or key not in current_keys:
            continue
        game_pk, pitcher_id, _, _ = key
        arsenal_row = arsenal_rows.get((game_pk, pitcher_id))
        if arsenal_row is None:
            continue
        rows.append(score_one_context(whiff_row, arsenal_row))
    return pd.DataFrame(rows, columns=COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture preregistered report-only pitch-mix Whiff scores.")
    parser.add_argument("--whiff-context", default="data/batter_pitch_whiff_context_log.csv")
    parser.add_argument("--arsenal-context", default="data/pitch_arsenal_context_log.csv")
    parser.add_argument("--hand-context", default="data/handedness_matchup_effective_context.csv")
    parser.add_argument("--output", default="data/pitch_mix_whiff_score_log.csv")
    args = parser.parse_args()

    whiff = pd.read_csv(args.whiff_context) if Path(args.whiff_context).exists() else pd.DataFrame()
    arsenal = pd.read_csv(args.arsenal_context) if Path(args.arsenal_context).exists() else pd.DataFrame()
    hand = pd.read_csv(args.hand_context) if Path(args.hand_context).exists() else pd.DataFrame()
    result = build_score_frame(whiff, arsenal, hand)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False)
    eligible = int(result.get("audit_eligible", pd.Series(dtype=bool)).map(_truthy).sum()) if not result.empty else 0
    print(
        f"pitch_mix_whiff_score_rows={len(result)} eligible_rows={eligible} "
        f"formula={FORMULA_ID} report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY}"
    )


if __name__ == "__main__":
    main()
