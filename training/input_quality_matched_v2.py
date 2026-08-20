from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

AUDIT_VERSION = "input-quality-matched-v2-report-only"
PRODUCTION_AUTHORITY = "NONE"
FUTURE_ONLY_START = pd.Timestamp("2026-08-20")
SHALLOW_MAX_HISTORY = 4
DEEP_MIN_HISTORY = 5
MIN_MATCHED_PAIRS = 20

METRICS = {
    "STRIKEOUTS": ("projection", "actual_strikeouts"),
    "HITS": ("hits_projection", "actual_hits_allowed"),
    "OUTS": ("outs_projection", "actual_outs"),
}


@dataclass(frozen=True)
class MatchRule:
    name: str
    projection_caliper: float
    workload_caliper: float
    opponent_k_caliper: float
    require_same_role: bool = True
    require_same_pitcher: bool = False


PRIMARY_RULE = MatchRule(
    name="primary_pregame_matched",
    projection_caliper=0.75,
    workload_caliper=1.5,
    opponent_k_caliper=2.0,
)
SAME_PITCHER_RULE = MatchRule(
    name="same_pitcher_sensitivity",
    projection_caliper=1.00,
    workload_caliper=2.0,
    opponent_k_caliper=3.0,
    require_same_pitcher=True,
)

PAIR_COLUMNS = [
    "Audit_Version", "Production_Authority", "Rule", "Metric", "Pair_ID",
    "Shallow_Game_Date", "Deep_Game_Date", "Shallow_Pitcher", "Deep_Pitcher",
    "Shallow_Pitcher_ID", "Deep_Pitcher_ID", "Shallow_History", "Deep_History",
    "Shallow_Projection", "Deep_Projection", "Shallow_Expected_Outs", "Deep_Expected_Outs",
    "Shallow_Opponent_K_Pct", "Deep_Opponent_K_Pct", "Shallow_Role", "Deep_Role",
    "Projection_Diff", "Expected_Outs_Diff", "Opponent_K_Pct_Diff",
    "Shallow_Error", "Deep_Error", "Shallow_Absolute_Error", "Deep_Absolute_Error",
    "Absolute_Error_Delta_Shallow_Minus_Deep",
]

SUMMARY_COLUMNS = [
    "Audit_Version", "Production_Authority", "Rule", "Metric", "Eligible_Shallow",
    "Eligible_Deep", "Matched_Pairs", "Shallow_MAE", "Deep_MAE",
    "Relative_MAE_Improvement_Deep_vs_Shallow", "Shallow_Bias", "Deep_Bias",
    "Status", "Future_Only_Start", "Min_Matched_Pairs",
]


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _text(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype=str)
    return frame[column].fillna("").astype(str).str.strip()


def _role_bucket(frame: pd.DataFrame) -> pd.Series:
    explicit = _text(frame, "starter_role_label").str.upper()
    expected_outs = _num(frame, "expected_outs")
    fallback = pd.Series("UNKNOWN", index=frame.index, dtype=str)
    fallback.loc[expected_outs.ge(17)] = "FULL"
    fallback.loc[expected_outs.between(14, 16.999, inclusive="both")] = "MID"
    fallback.loc[expected_outs.lt(14)] = "SHORT"
    return explicit.where(explicit.ne(""), fallback)


def prepare_future_cohort(frame: pd.DataFrame) -> pd.DataFrame:
    """Return only outcome-eligible, future OOS rows with pregame matching fields."""
    if frame is None or frame.empty:
        return pd.DataFrame()
    work = frame.copy()
    dates = pd.to_datetime(work.get("game_date"), errors="coerce").dt.normalize()
    work["_game_date"] = dates
    work["_history"] = _num(work, "starter_history_games")
    work["_expected_outs"] = _num(work, "expected_outs")
    work["_opponent_k_pct"] = _num(work, "opponent_k_pct")
    work["_role"] = _role_bucket(work)
    work["_pitcher"] = _text(work, "player")
    work["_pitcher_id"] = _text(work, "pitcher_id")
    work = work.loc[
        work["_game_date"].ge(FUTURE_ONLY_START)
        & work["_history"].notna()
        & work["_expected_outs"].notna()
        & work["_opponent_k_pct"].notna()
    ].copy()
    return work.sort_values(["_game_date", "_pitcher_id", "_pitcher"], kind="stable")


def _candidate_cost(shallow: pd.Series, deep: pd.Series, rule: MatchRule) -> float | None:
    projection_diff = abs(float(shallow["_projection"]) - float(deep["_projection"]))
    workload_diff = abs(float(shallow["_expected_outs"]) - float(deep["_expected_outs"]))
    opponent_k_diff = abs(float(shallow["_opponent_k_pct"]) - float(deep["_opponent_k_pct"]))
    if projection_diff > rule.projection_caliper:
        return None
    if workload_diff > rule.workload_caliper:
        return None
    if opponent_k_diff > rule.opponent_k_caliper:
        return None
    if rule.require_same_role and str(shallow["_role"]) != str(deep["_role"]):
        return None
    if rule.require_same_pitcher:
        shallow_id, deep_id = str(shallow["_pitcher_id"]), str(deep["_pitcher_id"])
        same_id = bool(shallow_id and deep_id and shallow_id == deep_id)
        same_name = str(shallow["_pitcher"]).lower() == str(deep["_pitcher"]).lower()
        if not (same_id or same_name):
            return None
    # Normalize by frozen calipers; deterministic tie-breaking happens later.
    return (
        projection_diff / rule.projection_caliper
        + workload_diff / rule.workload_caliper
        + opponent_k_diff / rule.opponent_k_caliper
    )


def match_metric(frame: pd.DataFrame, metric: str, rule: MatchRule = PRIMARY_RULE) -> pd.DataFrame:
    metric = str(metric).upper()
    if metric not in METRICS:
        raise ValueError(f"Unsupported metric: {metric}")
    prepared = prepare_future_cohort(frame)
    if prepared.empty:
        return pd.DataFrame(columns=PAIR_COLUMNS)
    prediction_column, actual_column = METRICS[metric]
    prepared["_projection"] = _num(prepared, prediction_column)
    prepared["_actual"] = _num(prepared, actual_column)
    ready = prepared.loc[prepared["_projection"].notna() & prepared["_actual"].notna()].copy()
    shallow = ready.loc[ready["_history"].le(SHALLOW_MAX_HISTORY)].copy()
    deep = ready.loc[ready["_history"].ge(DEEP_MIN_HISTORY)].copy()
    if shallow.empty or deep.empty:
        return pd.DataFrame(columns=PAIR_COLUMNS)

    candidate_edges: list[tuple[float, str, str, int, int]] = []
    for shallow_idx, shallow_row in shallow.iterrows():
        for deep_idx, deep_row in deep.iterrows():
            cost = _candidate_cost(shallow_row, deep_row, rule)
            if cost is None:
                continue
            candidate_edges.append((
                cost,
                str(shallow_row["_game_date"]),
                str(deep_row["_game_date"]),
                int(shallow_idx),
                int(deep_idx),
            ))
    candidate_edges.sort()

    used_shallow: set[int] = set()
    used_deep: set[int] = set()
    rows: list[dict[str, object]] = []
    for _, _, _, shallow_idx, deep_idx in candidate_edges:
        if shallow_idx in used_shallow or deep_idx in used_deep:
            continue
        s, d = ready.loc[shallow_idx], ready.loc[deep_idx]
        used_shallow.add(shallow_idx)
        used_deep.add(deep_idx)
        s_error = float(s["_projection"] - s["_actual"])
        d_error = float(d["_projection"] - d["_actual"])
        rows.append({
            "Audit_Version": AUDIT_VERSION,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "Rule": rule.name,
            "Metric": metric,
            "Pair_ID": len(rows) + 1,
            "Shallow_Game_Date": s["_game_date"].date().isoformat(),
            "Deep_Game_Date": d["_game_date"].date().isoformat(),
            "Shallow_Pitcher": s["_pitcher"],
            "Deep_Pitcher": d["_pitcher"],
            "Shallow_Pitcher_ID": s["_pitcher_id"],
            "Deep_Pitcher_ID": d["_pitcher_id"],
            "Shallow_History": float(s["_history"]),
            "Deep_History": float(d["_history"]),
            "Shallow_Projection": float(s["_projection"]),
            "Deep_Projection": float(d["_projection"]),
            "Shallow_Expected_Outs": float(s["_expected_outs"]),
            "Deep_Expected_Outs": float(d["_expected_outs"]),
            "Shallow_Opponent_K_Pct": float(s["_opponent_k_pct"]),
            "Deep_Opponent_K_Pct": float(d["_opponent_k_pct"]),
            "Shallow_Role": s["_role"],
            "Deep_Role": d["_role"],
            "Projection_Diff": abs(float(s["_projection"] - d["_projection"])),
            "Expected_Outs_Diff": abs(float(s["_expected_outs"] - d["_expected_outs"])),
            "Opponent_K_Pct_Diff": abs(float(s["_opponent_k_pct"] - d["_opponent_k_pct"])),
            "Shallow_Error": s_error,
            "Deep_Error": d_error,
            "Shallow_Absolute_Error": abs(s_error),
            "Deep_Absolute_Error": abs(d_error),
            "Absolute_Error_Delta_Shallow_Minus_Deep": abs(s_error) - abs(d_error),
        })
    return pd.DataFrame(rows, columns=PAIR_COLUMNS)


def summarize_rule(frame: pd.DataFrame, metric: str, rule: MatchRule = PRIMARY_RULE) -> pd.DataFrame:
    prepared = prepare_future_cohort(frame)
    prediction_column, actual_column = METRICS[str(metric).upper()]
    if prepared.empty:
        eligible_shallow = eligible_deep = 0
    else:
        projection = _num(prepared, prediction_column)
        actual = _num(prepared, actual_column)
        ready = projection.notna() & actual.notna()
        eligible_shallow = int((ready & prepared["_history"].le(SHALLOW_MAX_HISTORY)).sum())
        eligible_deep = int((ready & prepared["_history"].ge(DEEP_MIN_HISTORY)).sum())
    pairs = match_metric(frame, metric, rule)
    n_pairs = int(len(pairs))
    if n_pairs:
        shallow_mae = float(pd.to_numeric(pairs["Shallow_Absolute_Error"], errors="coerce").mean())
        deep_mae = float(pd.to_numeric(pairs["Deep_Absolute_Error"], errors="coerce").mean())
        shallow_bias = float(pd.to_numeric(pairs["Shallow_Error"], errors="coerce").mean())
        deep_bias = float(pd.to_numeric(pairs["Deep_Error"], errors="coerce").mean())
        relative = float((shallow_mae - deep_mae) / shallow_mae) if shallow_mae > 0 else np.nan
    else:
        shallow_mae = deep_mae = shallow_bias = deep_bias = relative = np.nan

    if n_pairs < MIN_MATCHED_PAIRS:
        status = "LEARNING"
    elif relative >= 0.01 and abs(deep_bias) <= abs(shallow_bias):
        status = "SUPPORTIVE"
    elif relative <= -0.01 and abs(deep_bias) >= abs(shallow_bias):
        status = "CONTRADICTORY"
    else:
        status = "MIXED"

    return pd.DataFrame([{
        "Audit_Version": AUDIT_VERSION,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "Rule": rule.name,
        "Metric": str(metric).upper(),
        "Eligible_Shallow": eligible_shallow,
        "Eligible_Deep": eligible_deep,
        "Matched_Pairs": n_pairs,
        "Shallow_MAE": shallow_mae,
        "Deep_MAE": deep_mae,
        "Relative_MAE_Improvement_Deep_vs_Shallow": relative,
        "Shallow_Bias": shallow_bias,
        "Deep_Bias": deep_bias,
        "Status": status,
        "Future_Only_Start": FUTURE_ONLY_START.date().isoformat(),
        "Min_Matched_Pairs": MIN_MATCHED_PAIRS,
    }], columns=SUMMARY_COLUMNS)


def run_audit(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    pair_frames: list[pd.DataFrame] = []
    summary_frames: list[pd.DataFrame] = []
    for rule in (PRIMARY_RULE, SAME_PITCHER_RULE):
        for metric in METRICS:
            pair_frames.append(match_metric(frame, metric, rule))
            summary_frames.append(summarize_rule(frame, metric, rule))
    pairs = pd.concat(pair_frames, ignore_index=True) if pair_frames else pd.DataFrame(columns=PAIR_COLUMNS)
    summary = pd.concat(summary_frames, ignore_index=True) if summary_frames else pd.DataFrame(columns=SUMMARY_COLUMNS)
    return pairs, summary


def preregistration_manifest() -> pd.DataFrame:
    rows = [
        ("audit_version", AUDIT_VERSION),
        ("production_authority", PRODUCTION_AUTHORITY),
        ("future_only_start", FUTURE_ONLY_START.date().isoformat()),
        ("shallow_history_definition", f"starter_history_games <= {SHALLOW_MAX_HISTORY}"),
        ("deep_history_definition", f"starter_history_games >= {DEEP_MIN_HISTORY}"),
        ("minimum_matched_pairs", MIN_MATCHED_PAIRS),
        ("primary_projection_caliper", PRIMARY_RULE.projection_caliper),
        ("primary_expected_outs_caliper", PRIMARY_RULE.workload_caliper),
        ("primary_opponent_k_pct_caliper", PRIMARY_RULE.opponent_k_caliper),
        ("primary_same_role_required", PRIMARY_RULE.require_same_role),
        ("same_pitcher_sensitivity_enabled", True),
        ("matching_replacement", False),
        ("pairing_uses_outcomes", False),
        ("weather_authority", "INFORMATIONAL_ONLY"),
    ]
    return pd.DataFrame(rows, columns=["Field", "Frozen_Value"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Preregistered report-only matched-cohort Input Quality Audit v2")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--pairs", type=Path, default=Path("data/input_quality_matched_v2_pairs.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/input_quality_matched_v2_summary.csv"))
    parser.add_argument("--preregistration", type=Path, default=Path("data/input_quality_matched_v2_preregistration.csv"))
    args = parser.parse_args()
    frame = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    pairs, summary = run_audit(frame)
    manifest = preregistration_manifest()
    for path in (args.pairs, args.summary, args.preregistration):
        path.parent.mkdir(parents=True, exist_ok=True)
    pairs.to_csv(args.pairs, index=False)
    summary.to_csv(args.summary, index=False)
    manifest.to_csv(args.preregistration, index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
