from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from training.opponent_matchup_validation import build_detail

VERSION = "opponent-matchup-boost-stress-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"

MIN_BOOST_STARTS = 60
MIN_BOOST_DAYS = 10
MIN_BOOST_OPPONENTS = 12
MIN_SUPPORT_RELATIVE_MAE = 0.005
MIN_SUPPORT_WIN_SHARE = 0.52
BIAS_WORSEN_TOLERANCE = 0.05
MIN_SEGMENT_READ_STARTS = 8

DETAIL_COLUMNS = [
    "game_date", "game_pk", "pitcher_id", "player", "team", "opponent",
    "Opponent_K_Rate", "Opponent_K_Delta_PP", "Opponent_K_Extremity",
    "Matchup_PA", "Matchup_PA_Band", "Matchup_Batters", "Lineup_State",
    "Data_Quality", "Quality_Band", "Neutral_Opponent_Projection",
    "Neutral_K_Projection_Level", "Applied_Projection", "Matchup_Adjustment_K",
    "Boost_Magnitude_Band", "Actual_Strikeouts", "Applied_Absolute_Error",
    "Neutral_Absolute_Error", "Applied_Error", "Neutral_Error", "Applied_Win",
    "Neutral_Win", "Tie", "Applied_Overprediction", "Neutral_Overprediction",
    "Report_Only", "Production_Authority", "Validation_Version",
]

SUMMARY_COLUMNS = [
    "Finding", "Early_Read", "Boost_Starts", "Observed_Days", "Distinct_Opponents",
    "Applied_MAE", "Neutral_MAE", "Relative_MAE_Improvement", "Applied_Win_Share",
    "Neutral_Win_Share", "Tie_Share", "Applied_Bias", "Neutral_Bias",
    "Bias_Abs_Change", "Applied_Overprediction_Rate", "Neutral_Overprediction_Rate",
    "Overprediction_Rate_Change", "Mean_Boost_K", "Median_Boost_K",
    "Mean_Opponent_K_Delta_PP", "Mean_Matchup_PA", "Reason", "Recommended_Action",
    "Manual_Review_Ready", "Report_Only", "Production_Authority", "Validation_Version",
]
SEGMENT_COLUMNS = [
    "Dimension", "Segment", "Boost_Starts", "Observed_Days", "Distinct_Opponents",
    "Applied_MAE", "Neutral_MAE", "Relative_MAE_Improvement", "Applied_Win_Share",
    "Neutral_Win_Share", "Tie_Share", "Applied_Bias", "Neutral_Bias",
    "Bias_Abs_Change", "Applied_Overprediction_Rate", "Neutral_Overprediction_Rate",
    "Overprediction_Rate_Change", "Mean_Boost_K", "Median_Boost_K",
    "Mean_Opponent_K_Delta_PP", "Mean_Matchup_PA", "Stress_Read",
    "Report_Only", "Production_Authority", "Validation_Version",
]
GATE_COLUMNS = SUMMARY_COLUMNS


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _boolish(frame: pd.DataFrame, column: str) -> pd.Series:
    raw = frame.get(column, pd.Series(False, index=frame.index))
    return raw.fillna(False).astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def _opponent_extremity(delta_pp: float) -> str:
    if not np.isfinite(delta_pp):
        return "UNKNOWN"
    if delta_pp < 1.0:
        return "+0.25–0.99pp"
    if delta_pp < 1.5:
        return "+1.00–1.49pp"
    if delta_pp < 2.5:
        return "+1.50–2.49pp"
    return "+2.50pp+"


def _boost_magnitude(delta_k: float) -> str:
    if not np.isfinite(delta_k):
        return "UNKNOWN"
    if delta_k < 0.10:
        return "<0.10 K"
    if delta_k < 0.25:
        return "0.10–0.24 K"
    if delta_k < 0.40:
        return "0.25–0.39 K"
    return "0.40+ K"


def _neutral_projection_level(value: float) -> str:
    if not np.isfinite(value):
        return "UNKNOWN"
    if value < 4.0:
        return "<4.0 K"
    if value < 5.0:
        return "4.0–4.99 K"
    if value < 6.0:
        return "5.0–5.99 K"
    return "6.0+ K"


def _matchup_pa_band(value: float) -> str:
    if not np.isfinite(value):
        return "UNKNOWN"
    if value < 1000:
        return "<1,000 PA"
    if value < 2000:
        return "1,000–1,999 PA"
    if value < 3000:
        return "2,000–2,999 PA"
    return "3,000+ PA"


def build_boost_detail(matchup_detail: pd.DataFrame) -> pd.DataFrame:
    """Keep only authentic, informative positive opponent-K adjustments.

    Source columns come from the v2 analytic-ablation detail. Segment labels use
    only pregame information; final strikeouts are used solely for scoring.
    """
    if matchup_detail is None or matchup_detail.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    source = matchup_detail.copy()
    auditable = _boolish(source, "Auditable")
    direction = source.get("Adjustment_Direction", pd.Series("", index=source.index)).astype(str).str.upper()
    boost = source.loc[auditable & direction.eq("BOOST")].copy()
    if boost.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    delta_pp = _num(boost, "Opponent_K_Delta_PP")
    adjustment = _num(boost, "Matchup_Adjustment_K")
    neutral = _num(boost, "Neutral_Opponent_Projection")
    matchup_pa = _num(boost, "Matchup_PA")
    applied_error = _num(boost, "Applied_Error")
    neutral_error = _num(boost, "Neutral_Error")

    boost["Opponent_K_Extremity"] = [_opponent_extremity(float(x)) for x in delta_pp]
    boost["Boost_Magnitude_Band"] = [_boost_magnitude(float(x)) for x in adjustment]
    boost["Neutral_K_Projection_Level"] = [_neutral_projection_level(float(x)) for x in neutral]
    boost["Matchup_PA_Band"] = [_matchup_pa_band(float(x)) for x in matchup_pa]
    boost["Applied_Overprediction"] = applied_error.gt(0.0)
    boost["Neutral_Overprediction"] = neutral_error.gt(0.0)
    boost["Report_Only"] = REPORT_ONLY
    boost["Production_Authority"] = PRODUCTION_AUTHORITY
    boost["Validation_Version"] = VERSION

    for column in DETAIL_COLUMNS:
        if column not in boost.columns:
            boost[column] = np.nan
    return boost[DETAIL_COLUMNS].reset_index(drop=True)


def _empty_metrics() -> dict[str, object]:
    return {
        "Boost_Starts": 0,
        "Observed_Days": 0,
        "Distinct_Opponents": 0,
        "Applied_MAE": np.nan,
        "Neutral_MAE": np.nan,
        "Relative_MAE_Improvement": np.nan,
        "Applied_Win_Share": np.nan,
        "Neutral_Win_Share": np.nan,
        "Tie_Share": np.nan,
        "Applied_Bias": np.nan,
        "Neutral_Bias": np.nan,
        "Bias_Abs_Change": np.nan,
        "Applied_Overprediction_Rate": np.nan,
        "Neutral_Overprediction_Rate": np.nan,
        "Overprediction_Rate_Change": np.nan,
        "Mean_Boost_K": np.nan,
        "Median_Boost_K": np.nan,
        "Mean_Opponent_K_Delta_PP": np.nan,
        "Mean_Matchup_PA": np.nan,
    }


def _metrics(group: pd.DataFrame) -> dict[str, object]:
    if group is None or group.empty:
        return _empty_metrics()

    n = int(len(group))
    days = int(group["game_date"].replace("", np.nan).dropna().astype(str).nunique())
    opponents = int(group["opponent"].replace("", np.nan).dropna().astype(str).nunique())
    applied_mae = float(_num(group, "Applied_Absolute_Error").mean())
    neutral_mae = float(_num(group, "Neutral_Absolute_Error").mean())
    if neutral_mae > 0:
        relative = float((neutral_mae - applied_mae) / neutral_mae)
    elif neutral_mae == 0 and applied_mae == 0:
        relative = 0.0
    else:
        relative = np.nan
    applied_win = float(_boolish(group, "Applied_Win").mean())
    neutral_win = float(_boolish(group, "Neutral_Win").mean())
    tie = float(_boolish(group, "Tie").mean())
    applied_bias = float(_num(group, "Applied_Error").mean())
    neutral_bias = float(_num(group, "Neutral_Error").mean())
    bias_abs_change = float(abs(applied_bias) - abs(neutral_bias))
    applied_over = float(_boolish(group, "Applied_Overprediction").mean())
    neutral_over = float(_boolish(group, "Neutral_Overprediction").mean())
    return {
        "Boost_Starts": n,
        "Observed_Days": days,
        "Distinct_Opponents": opponents,
        "Applied_MAE": applied_mae,
        "Neutral_MAE": neutral_mae,
        "Relative_MAE_Improvement": relative,
        "Applied_Win_Share": applied_win,
        "Neutral_Win_Share": neutral_win,
        "Tie_Share": tie,
        "Applied_Bias": applied_bias,
        "Neutral_Bias": neutral_bias,
        "Bias_Abs_Change": bias_abs_change,
        "Applied_Overprediction_Rate": applied_over,
        "Neutral_Overprediction_Rate": neutral_over,
        "Overprediction_Rate_Change": float(applied_over - neutral_over),
        "Mean_Boost_K": float(_num(group, "Matchup_Adjustment_K").mean()),
        "Median_Boost_K": float(_num(group, "Matchup_Adjustment_K").median()),
        "Mean_Opponent_K_Delta_PP": float(_num(group, "Opponent_K_Delta_PP").mean()),
        "Mean_Matchup_PA": float(_num(group, "Matchup_PA").mean()),
    }


def _perfect_neutral_failure(metrics: dict[str, object]) -> bool:
    neutral_mae = metrics["Neutral_MAE"]
    applied_mae = metrics["Applied_MAE"]
    return bool(
        pd.notna(neutral_mae)
        and pd.notna(applied_mae)
        and float(neutral_mae) == 0.0
        and float(applied_mae) > 0.0
    )


def _early_read(metrics: dict[str, object]) -> str:
    if int(metrics["Boost_Starts"]) < 10:
        return "SMALL_SAMPLE"
    if _perfect_neutral_failure(metrics):
        return "LEAN_TOO_HOT"

    rel = metrics["Relative_MAE_Improvement"]
    win = metrics["Applied_Win_Share"]
    bias_change = metrics["Bias_Abs_Change"]
    if pd.notna(rel) and pd.notna(win) and pd.notna(bias_change):
        if float(rel) < 0.0 and (float(win) <= 0.50 or float(bias_change) > BIAS_WORSEN_TOLERANCE):
            return "LEAN_TOO_HOT"
        if (
            float(rel) >= MIN_SUPPORT_RELATIVE_MAE
            and float(win) >= MIN_SUPPORT_WIN_SHARE
            and float(bias_change) <= BIAS_WORSEN_TOLERANCE
        ):
            return "LEAN_SUPPORTED"
    return "MIXED"


def _formal_finding(metrics: dict[str, object]) -> tuple[str, str, str, bool]:
    n = int(metrics["Boost_Starts"])
    days = int(metrics["Observed_Days"])
    opponents = int(metrics["Distinct_Opponents"])
    early = _early_read(metrics)
    if n < MIN_BOOST_STARTS or days < MIN_BOOST_DAYS or opponents < MIN_BOOST_OPPONENTS:
        return (
            "INCONCLUSIVE",
            f"Need at least {MIN_BOOST_STARTS} boost starts, {MIN_BOOST_DAYS} observed days, and {MIN_BOOST_OPPONENTS} opponents; have {n}, {days}, and {opponents}. Early read: {early}.",
            "KEEP_CURRENT_BOOST_AND_LEARN",
            False,
        )

    if _perfect_neutral_failure(metrics):
        return (
            "TOO HOT",
            "The neutral-opponent counterfactual is perfect in this evaluation sample while the positive boost adds error. This is a manual-review signal only.",
            "MANUAL_REVIEW_DO_NOT_RETUNE_AUTOMATICALLY",
            True,
        )

    rel = metrics["Relative_MAE_Improvement"]
    win = metrics["Applied_Win_Share"]
    bias_change = metrics["Bias_Abs_Change"]
    if pd.isna(rel) or pd.isna(win) or pd.isna(bias_change):
        return (
            "INCONCLUSIVE",
            "Boost sample is large enough, but required scoring metrics are incomplete.",
            "KEEP_CURRENT_BOOST_AND_LEARN",
            False,
        )

    if (
        float(rel) >= MIN_SUPPORT_RELATIVE_MAE
        and float(win) >= MIN_SUPPORT_WIN_SHARE
        and float(bias_change) <= BIAS_WORSEN_TOLERANCE
    ):
        return (
            "SUPPORTED",
            "Positive matchup boosts clear MAE, head-to-head win-share, and absolute-bias guardrails versus the neutral-opponent counterfactual.",
            "KEEP_CURRENT_BOOST",
            True,
        )

    too_hot_votes = sum((
        float(rel) < 0.0,
        float(win) < 0.50,
        float(bias_change) > BIAS_WORSEN_TOLERANCE,
    ))
    if too_hot_votes >= 2:
        return (
            "TOO HOT",
            "Positive matchup boosts fail at least two of the MAE, head-to-head, and absolute-bias guardrails versus neutral. This is a manual-review signal only.",
            "MANUAL_REVIEW_DO_NOT_RETUNE_AUTOMATICALLY",
            True,
        )

    return (
        "INCONCLUSIVE",
        "The boost sample is large and time-diverse, but the evidence is mixed rather than clearly supported or clearly too hot.",
        "KEEP_CURRENT_BOOST_PENDING_MANUAL_REVIEW",
        False,
    )


def _segment_read(metrics: dict[str, object]) -> str:
    if int(metrics["Boost_Starts"]) < MIN_SEGMENT_READ_STARTS:
        return "SMALL_SAMPLE"
    if _perfect_neutral_failure(metrics):
        return "HURTING"
    rel = metrics["Relative_MAE_Improvement"]
    win = metrics["Applied_Win_Share"]
    bias_change = metrics["Bias_Abs_Change"]
    if pd.isna(rel) or pd.isna(win) or pd.isna(bias_change):
        return "MIXED"
    if float(rel) <= -0.005 and (float(win) < 0.50 or float(bias_change) > BIAS_WORSEN_TOLERANCE):
        return "HURTING"
    if float(rel) >= 0.005 and float(win) > 0.50 and float(bias_change) <= BIAS_WORSEN_TOLERANCE:
        return "HELPING"
    return "MIXED"


def summarize(boost_detail: pd.DataFrame) -> pd.DataFrame:
    metrics = _metrics(boost_detail)
    finding, reason, action, review_ready = _formal_finding(metrics)
    row = {
        "Finding": finding,
        "Early_Read": _early_read(metrics),
        **metrics,
        "Reason": reason,
        "Recommended_Action": action,
        "Manual_Review_Ready": review_ready,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "Validation_Version": VERSION,
    }
    return pd.DataFrame([row], columns=SUMMARY_COLUMNS)


def evaluate_gate(boost_detail: pd.DataFrame) -> pd.DataFrame:
    return summarize(boost_detail)[GATE_COLUMNS].copy()


def build_segments(boost_detail: pd.DataFrame) -> pd.DataFrame:
    if boost_detail is None or boost_detail.empty:
        return pd.DataFrame(columns=SEGMENT_COLUMNS)

    rows: list[dict[str, object]] = []

    def add(dimension: str, segment: str, group: pd.DataFrame) -> None:
        metrics = _metrics(group)
        rows.append({
            "Dimension": dimension,
            "Segment": segment,
            **metrics,
            "Stress_Read": _segment_read(metrics),
            "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "Validation_Version": VERSION,
        })

    add("OVERALL", "ALL AUDITABLE BOOSTS", boost_detail)
    for dimension, column in (
        ("OPPONENT K EXTREMITY", "Opponent_K_Extremity"),
        ("BOOST MAGNITUDE", "Boost_Magnitude_Band"),
        ("LINEUP STATE", "Lineup_State"),
        ("NEUTRAL K PROJECTION LEVEL", "Neutral_K_Projection_Level"),
        ("MATCHUP PA", "Matchup_PA_Band"),
        ("QUALITY BAND", "Quality_Band"),
    ):
        values = boost_detail[column].fillna("UNKNOWN").astype(str)
        for segment in sorted(values.unique()):
            add(dimension, segment, boost_detail.loc[values.eq(segment)].copy())
    return pd.DataFrame(rows, columns=SEGMENT_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-only positive opponent-K boost stress test")
    parser.add_argument("--source-detail", type=Path, default=Path("data/opponent_matchup_validation_detail.csv"))
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/opponent_matchup_boost_stress_detail.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/opponent_matchup_boost_stress_summary.csv"))
    parser.add_argument("--segments", type=Path, default=Path("data/opponent_matchup_boost_stress_segments.csv"))
    parser.add_argument("--gate", type=Path, default=Path("data/opponent_matchup_boost_stress_gate.csv"))
    args = parser.parse_args()

    if args.source_detail.exists():
        matchup_detail = pd.read_csv(args.source_detail)
    elif args.projection_log.exists():
        matchup_detail = build_detail(pd.read_csv(args.projection_log))
    else:
        raise SystemExit("No opponent matchup detail or projection history available")

    boost_detail = build_boost_detail(matchup_detail)
    summary = summarize(boost_detail)
    segments = build_segments(boost_detail)
    gate = evaluate_gate(boost_detail)
    for path in (args.detail, args.summary, args.segments, args.gate):
        path.parent.mkdir(parents=True, exist_ok=True)
    boost_detail.to_csv(args.detail, index=False)
    summary.to_csv(args.summary, index=False)
    segments.to_csv(args.segments, index=False)
    gate.to_csv(args.gate, index=False)
    print(summary.to_string(index=False))
    print(gate.to_string(index=False))
    print(f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY}")


if __name__ == "__main__":
    main()
