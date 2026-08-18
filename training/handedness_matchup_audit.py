from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "handedness-matchup-audit-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"

MIN_STARTS = 60
MIN_DAYS = 10
MIN_OPPONENTS = 15
MIN_RHP_STARTS = 35
MIN_LHP_STARTS = 15
MIN_SEGMENT_READ = 8
ASYMMETRY_REL_GAP = 0.01
ASYMMETRY_WIN_GAP = 0.10

DETAIL_COLUMNS = [
    "game_date", "game_pk", "pitcher_id", "player", "team", "opponent",
    "pitcher_hand", "lineup_source", "lineup_confirmed", "lineup_hash",
    "hand_context_captured_at_utc", "lineage", "split_coverage",
    "split_available_batters", "split_unavailable_batters", "same_hand_batters",
    "opposite_hand_batters", "opposite_hand_share", "Applied_Projection",
    "Neutral_Opponent_Projection", "Matchup_Adjustment_K", "Adjustment_Direction",
    "Actual_Strikeouts", "Applied_Absolute_Error", "Neutral_Absolute_Error",
    "Applied_Error", "Neutral_Error", "Applied_Win", "Neutral_Win", "Tie",
    "Report_Only", "Production_Authority", "Validation_Version",
]

SEGMENT_COLUMNS = [
    "Dimension", "Segment", "Starts", "Observed_Days", "Distinct_Opponents",
    "Applied_MAE", "Neutral_MAE", "Relative_MAE_Improvement", "Applied_Win_Share",
    "Neutral_Win_Share", "Tie_Share", "Applied_Bias", "Neutral_Bias",
    "Applied_Abs_Bias_Change_vs_Neutral", "Mean_Adjustment_K", "Mean_Split_Coverage",
    "Mean_Opposite_Hand_Share", "Evidence", "Report_Only", "Production_Authority",
    "Validation_Version",
]

GATE_COLUMNS = [
    "Finding", "Early_Read", "Auditable_Starts", "Observed_Days", "Distinct_Opponents",
    "RHP_Starts", "LHP_Starts", "RHP_Relative_MAE_Improvement",
    "LHP_Relative_MAE_Improvement", "RHP_Applied_Win_Share", "LHP_Applied_Win_Share",
    "Reason", "Recommended_Action", "Report_Only", "Production_Authority",
    "Validation_Version",
]


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _bool(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index, dtype=bool)
    raw = frame[column]
    if pd.api.types.is_bool_dtype(raw):
        return raw.fillna(False).astype(bool)
    return raw.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _safe_rel(neutral_mae: float, applied_mae: float) -> float:
    if not np.isfinite(neutral_mae) or neutral_mae <= 0 or not np.isfinite(applied_mae):
        return np.nan
    return float((neutral_mae - applied_mae) / neutral_mae)


def _latest_context(context: pd.DataFrame) -> pd.DataFrame:
    if context is None or context.empty:
        return pd.DataFrame()
    work = context.copy()
    work = work.loc[_bool(work, "audit_eligible")].copy()
    if work.empty:
        return work
    work["_game_pk"] = _num(work, "game_pk")
    work["_pitcher_id"] = _num(work, "pitcher_id")
    work["_captured"] = pd.to_datetime(work.get("hand_context_captured_at_utc"), errors="coerce", utc=True)
    work["_game_time"] = pd.to_datetime(work.get("game_time"), errors="coerce", utc=True)
    work = work.dropna(subset=["_game_pk", "_pitcher_id", "_captured", "_game_time"])
    work = work.loc[work["_captured"].lt(work["_game_time"])].copy()
    work = work.sort_values("_captured").drop_duplicates(["_game_pk", "_pitcher_id"], keep="last")
    return work


def build_detail(matchup_detail: pd.DataFrame, context_log: pd.DataFrame) -> pd.DataFrame:
    if matchup_detail is None or matchup_detail.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)
    context = _latest_context(context_log)
    if context.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    matchup = matchup_detail.copy()
    eligible = (
        _bool(matchup, "Auditable")
        & _bool(matchup, "Informative_Adjustment")
        & _num(matchup, "Actual_Strikeouts").notna()
        & _num(matchup, "Applied_Projection").notna()
        & _num(matchup, "Neutral_Opponent_Projection").notna()
    )
    matchup = matchup.loc[eligible].copy()
    if matchup.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)
    matchup["_game_pk"] = _num(matchup, "game_pk")
    matchup["_pitcher_id"] = _num(matchup, "pitcher_id")

    context_columns = [
        "_game_pk", "_pitcher_id", "pitcher_hand", "lineup_source", "lineup_confirmed",
        "lineup_hash", "hand_context_captured_at_utc", "lineage", "split_coverage",
        "split_available_batters", "split_unavailable_batters", "same_hand_batters",
        "opposite_hand_batters", "opposite_hand_share",
    ]
    merged = matchup.merge(context[context_columns], on=["_game_pk", "_pitcher_id"], how="inner")
    if merged.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    applied = _num(merged, "Applied_Projection")
    neutral = _num(merged, "Neutral_Opponent_Projection")
    actual = _num(merged, "Actual_Strikeouts")
    applied_abs = (applied - actual).abs()
    neutral_abs = (neutral - actual).abs()
    merged["Applied_Absolute_Error"] = applied_abs
    merged["Neutral_Absolute_Error"] = neutral_abs
    merged["Applied_Error"] = applied - actual
    merged["Neutral_Error"] = neutral - actual
    merged["Applied_Win"] = applied_abs.lt(neutral_abs)
    merged["Neutral_Win"] = neutral_abs.lt(applied_abs)
    merged["Tie"] = np.isclose(applied_abs, neutral_abs)
    merged["Report_Only"] = REPORT_ONLY
    merged["Production_Authority"] = PRODUCTION_AUTHORITY
    merged["Validation_Version"] = VERSION

    for column in DETAIL_COLUMNS:
        if column not in merged.columns:
            merged[column] = np.nan
    return merged[DETAIL_COLUMNS].reset_index(drop=True)


def _metrics(group: pd.DataFrame) -> dict[str, object]:
    if group is None or group.empty:
        return {
            "Starts": 0, "Observed_Days": 0, "Distinct_Opponents": 0,
            "Applied_MAE": np.nan, "Neutral_MAE": np.nan,
            "Relative_MAE_Improvement": np.nan, "Applied_Win_Share": np.nan,
            "Neutral_Win_Share": np.nan, "Tie_Share": np.nan,
            "Applied_Bias": np.nan, "Neutral_Bias": np.nan,
            "Applied_Abs_Bias_Change_vs_Neutral": np.nan,
            "Mean_Adjustment_K": np.nan, "Mean_Split_Coverage": np.nan,
            "Mean_Opposite_Hand_Share": np.nan,
        }
    applied_mae = float(_num(group, "Applied_Absolute_Error").mean())
    neutral_mae = float(_num(group, "Neutral_Absolute_Error").mean())
    applied_bias = float(_num(group, "Applied_Error").mean())
    neutral_bias = float(_num(group, "Neutral_Error").mean())
    return {
        "Starts": int(len(group)),
        "Observed_Days": int(group["game_date"].dropna().astype(str).nunique()),
        "Distinct_Opponents": int(group["opponent"].dropna().astype(str).nunique()),
        "Applied_MAE": applied_mae,
        "Neutral_MAE": neutral_mae,
        "Relative_MAE_Improvement": _safe_rel(neutral_mae, applied_mae),
        "Applied_Win_Share": float(group["Applied_Win"].astype(bool).mean()),
        "Neutral_Win_Share": float(group["Neutral_Win"].astype(bool).mean()),
        "Tie_Share": float(group["Tie"].astype(bool).mean()),
        "Applied_Bias": applied_bias,
        "Neutral_Bias": neutral_bias,
        "Applied_Abs_Bias_Change_vs_Neutral": float(abs(applied_bias) - abs(neutral_bias)),
        "Mean_Adjustment_K": float(_num(group, "Matchup_Adjustment_K").mean()),
        "Mean_Split_Coverage": float(_num(group, "split_coverage").mean()),
        "Mean_Opposite_Hand_Share": float(_num(group, "opposite_hand_share").mean()),
    }


def _coverage_band(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "UNKNOWN"
    if float(number) >= 0.999:
        return "FULL"
    if float(number) >= 0.75:
        return "HIGH_PARTIAL"
    return "LOW"


def _opposite_band(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "UNKNOWN"
    if float(number) < 0.45:
        return "<45%"
    if float(number) < 0.67:
        return "45–66%"
    return "67%+"


def build_segments(detail: pd.DataFrame) -> pd.DataFrame:
    if detail is None or detail.empty:
        return pd.DataFrame(columns=SEGMENT_COLUMNS)
    work = detail.copy()
    work["_coverage_band"] = work["split_coverage"].map(_coverage_band)
    work["_opposite_band"] = work["opposite_hand_share"].map(_opposite_band)
    work["_lineup_state"] = np.where(
        work["lineup_confirmed"].astype(str).str.lower().isin({"true", "1", "yes"}),
        "CONFIRMED", "ROSTER_FALLBACK"
    )
    dimensions = [
        ("OVERALL", pd.Series("ALL", index=work.index)),
        ("PITCHER HAND", work["pitcher_hand"].fillna("UNKNOWN").astype(str)),
        ("LINEUP STATE", work["_lineup_state"]),
        ("SPLIT COVERAGE", work["_coverage_band"]),
        ("OPPOSITE-HAND SHARE", work["_opposite_band"]),
        ("ADJUSTMENT DIRECTION", work["Adjustment_Direction"].fillna("UNKNOWN").astype(str)),
    ]
    rows: list[dict[str, object]] = []
    for dimension, labels in dimensions:
        for segment in pd.unique(labels):
            group = work.loc[labels.eq(segment)].copy()
            metrics = _metrics(group)
            n = int(metrics["Starts"])
            evidence = "LEARNING" if dimension == "OVERALL" or n < MIN_SEGMENT_READ else "DESCRIPTIVE"
            rows.append({
                "Dimension": dimension, "Segment": str(segment), **metrics,
                "Evidence": evidence, "Report_Only": REPORT_ONLY,
                "Production_Authority": PRODUCTION_AUTHORITY, "Validation_Version": VERSION,
            })
    return pd.DataFrame(rows, columns=SEGMENT_COLUMNS)


def _segment_row(segments: pd.DataFrame, hand: str) -> pd.Series | None:
    rows = segments.loc[
        segments["Dimension"].eq("PITCHER HAND") & segments["Segment"].eq(hand)
    ]
    return None if rows.empty else rows.iloc[0]


def build_gate(detail: pd.DataFrame, segments: pd.DataFrame) -> pd.DataFrame:
    total = _metrics(detail)
    rhp = _segment_row(segments, "R")
    lhp = _segment_row(segments, "L")
    r_n = 0 if rhp is None else int(rhp["Starts"])
    l_n = 0 if lhp is None else int(lhp["Starts"])
    r_rel = np.nan if rhp is None else rhp["Relative_MAE_Improvement"]
    l_rel = np.nan if lhp is None else lhp["Relative_MAE_Improvement"]
    r_win = np.nan if rhp is None else rhp["Applied_Win_Share"]
    l_win = np.nan if lhp is None else lhp["Applied_Win_Share"]

    early = "INCONCLUSIVE"
    if r_n >= MIN_SEGMENT_READ and l_n >= MIN_SEGMENT_READ and pd.notna(r_rel) and pd.notna(l_rel):
        if float(r_rel) >= 0 and float(l_rel) >= 0:
            early = "LEAN_CONSISTENT"
        elif float(r_rel) < 0 and float(l_rel) < 0:
            early = "LEAN_HURTING_BOTH"
        else:
            early = "LEAN_ASYMMETRY"

    ready = (
        int(total["Starts"]) >= MIN_STARTS
        and int(total["Observed_Days"]) >= MIN_DAYS
        and int(total["Distinct_Opponents"]) >= MIN_OPPONENTS
        and r_n >= MIN_RHP_STARTS
        and l_n >= MIN_LHP_STARTS
    )
    if not ready:
        finding = "LEARNING"
        reason = (
            f"Need {MIN_STARTS} starts, {MIN_DAYS} days, {MIN_OPPONENTS} opponents, "
            f"{MIN_RHP_STARTS} RHP starts, and {MIN_LHP_STARTS} LHP starts; have "
            f"{int(total['Starts'])}, {int(total['Observed_Days'])}, {int(total['Distinct_Opponents'])}, {r_n}, and {l_n}."
        )
        action = "KEEP_MATCHUP_HANDLING_UNCHANGED_AND_LEARN"
    else:
        rel_gap = abs(float(r_rel) - float(l_rel)) if pd.notna(r_rel) and pd.notna(l_rel) else np.nan
        win_gap = abs(float(r_win) - float(l_win)) if pd.notna(r_win) and pd.notna(l_win) else np.nan
        opposite_sign = pd.notna(r_rel) and pd.notna(l_rel) and float(r_rel) * float(l_rel) < 0
        if opposite_sign and ((pd.notna(rel_gap) and rel_gap >= ASYMMETRY_REL_GAP) or (pd.notna(win_gap) and win_gap >= ASYMMETRY_WIN_GAP)):
            finding = "ASYMMETRY_WATCH"
            reason = "RHP/LHP matchup value diverges enough to justify hand-specific research, not a production retune."
            action = "OPEN_HAND_SPECIFIC_REPORT_ONLY_RESEARCH"
        elif pd.notna(r_rel) and pd.notna(l_rel) and pd.notna(r_win) and pd.notna(l_win) and float(r_rel) >= 0 and float(l_rel) >= 0 and float(r_win) >= 0.50 and float(l_win) >= 0.50:
            finding = "CONSISTENT"
            reason = "Applied opponent matchup signal is directionally helpful for both pitcher hands at the audit gate."
            action = "KEEP_MATCHUP_HANDLING_UNCHANGED"
        elif pd.notna(r_rel) and pd.notna(l_rel) and pd.notna(r_win) and pd.notna(l_win) and float(r_rel) < 0 and float(l_rel) < 0 and float(r_win) < 0.50 and float(l_win) < 0.50:
            finding = "HURTING_BOTH"
            reason = "Applied opponent matchup signal hurts both pitcher-hand groups at the audit gate."
            action = "MANUAL_RESEARCH_REVIEW_ONLY"
        else:
            finding = "MIXED"
            reason = "Handedness audit clears sample gates but does not show a stable consistent or asymmetric pattern."
            action = "KEEP_MATCHUP_HANDLING_UNCHANGED_PENDING_MORE_EVIDENCE"

    return pd.DataFrame([{
        "Finding": finding, "Early_Read": early,
        "Auditable_Starts": int(total["Starts"]),
        "Observed_Days": int(total["Observed_Days"]),
        "Distinct_Opponents": int(total["Distinct_Opponents"]),
        "RHP_Starts": r_n, "LHP_Starts": l_n,
        "RHP_Relative_MAE_Improvement": r_rel,
        "LHP_Relative_MAE_Improvement": l_rel,
        "RHP_Applied_Win_Share": r_win, "LHP_Applied_Win_Share": l_win,
        "Reason": reason, "Recommended_Action": action,
        "Report_Only": REPORT_ONLY, "Production_Authority": PRODUCTION_AUTHORITY,
        "Validation_Version": VERSION,
    }], columns=GATE_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit production opponent matchup value by persisted pitcher-hand context.")
    parser.add_argument("--matchup-detail", default="data/opponent_matchup_validation_detail.csv")
    parser.add_argument("--context-log", default="data/handedness_matchup_context_log.csv")
    parser.add_argument("--detail-output", default="data/handedness_matchup_audit_detail.csv")
    parser.add_argument("--segments-output", default="data/handedness_matchup_audit_segments.csv")
    parser.add_argument("--gate-output", default="data/handedness_matchup_audit_gate.csv")
    args = parser.parse_args()

    matchup_path = Path(args.matchup_detail)
    context_path = Path(args.context_log)
    matchup = pd.read_csv(matchup_path) if matchup_path.exists() else pd.DataFrame()
    context = pd.read_csv(context_path) if context_path.exists() else pd.DataFrame()
    detail = build_detail(matchup, context)
    segments = build_segments(detail)
    gate = build_gate(detail, segments)
    for path, frame in (
        (Path(args.detail_output), detail),
        (Path(args.segments_output), segments),
        (Path(args.gate_output), gate),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    print(gate.to_string(index=False))
    print(f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY}")


if __name__ == "__main__":
    main()
