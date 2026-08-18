from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "opponent-matchup-weak-reduce-neutral-shadow-v1"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"

# Frozen from the REDUCE robustness stress result. This candidate neutralizes
# only the very mild suppressive environment that was slightly harmful in the
# derivation sample. Stronger suppressive opponent adjustments remain untouched.
FROZEN_DELTA_MIN_PP = -1.00
FROZEN_DELTA_MAX_PP = -0.25
DERIVATION_CUTOFF_DATE = "2026-08-17"

MIN_OOS_STARTS = 30
MIN_OOS_DAYS = 10
MIN_OOS_OPPONENTS = 12
MIN_SUPPORT_RELATIVE_MAE = 0.005
MIN_SUPPORT_WIN_SHARE = 0.52
BIAS_WORSEN_TOLERANCE = 0.05

DETAIL_COLUMNS = [
    "game_date", "game_pk", "pitcher_id", "player", "team", "opponent",
    "Opponent_K_Rate", "Opponent_K_Delta_PP", "Opponent_K_Extremity",
    "Matchup_PA", "Matchup_PA_Band", "Matchup_Batters", "Lineup_State",
    "Data_Quality", "Quality_Band", "Neutral_Opponent_Projection",
    "Neutral_K_Projection_Level", "Applied_Projection", "Matchup_Adjustment_K",
    "Reduction_Magnitude_K", "Reduction_Magnitude_Band", "Actual_Strikeouts",
    "Weak_Reduce_Eligible", "Neutralized_Projection", "Applied_Absolute_Error",
    "Neutralized_Absolute_Error", "Applied_Error", "Neutralized_Error",
    "Neutralized_Win_vs_Applied", "Applied_Win_vs_Neutralized",
    "Neutralized_Applied_Tie", "Evidence_Lane", "Counts_For_Promotion",
    "Report_Only", "Production_Authority", "Validation_Version",
]

SUMMARY_COLUMNS = [
    "Evidence_Lane", "Evidence_Status", "Starts", "Observed_Days",
    "Distinct_Opponents", "Applied_MAE", "Neutralized_MAE",
    "Neutralized_Relative_MAE_vs_Applied", "Neutralized_Win_Share_vs_Applied",
    "Applied_Win_Share_vs_Neutralized", "Tie_Share", "Applied_Bias",
    "Neutralized_Bias", "Neutralized_Bias_Abs_Change_vs_Applied",
    "Mean_Original_Reduction_K", "Mean_Opponent_K_Delta_PP",
    "Frozen_Delta_Min_PP", "Frozen_Delta_Max_PP", "Derivation_Cutoff_Date",
    "Reason", "Recommended_Action", "Report_Only", "Production_Authority",
    "Validation_Version",
]


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def build_detail(reduce_detail: pd.DataFrame) -> pd.DataFrame:
    """Build the frozen weak-REDUCE neutralization shadow detail.

    The source is already the authentic, auditable REDUCE-only stress detail.
    We further isolate the frozen weak suppressive band. Final strikeouts are
    used only for scoring; the candidate itself uses only pregame quantities.
    """
    if reduce_detail is None or reduce_detail.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    out = reduce_detail.copy()
    delta_pp = _num(out, "Opponent_K_Delta_PP")
    adjustment = _num(out, "Matchup_Adjustment_K")
    neutral = _num(out, "Neutral_Opponent_Projection")
    applied = _num(out, "Applied_Projection")
    actual = _num(out, "Actual_Strikeouts")

    weak_band = (
        adjustment.lt(0.0)
        & delta_pp.gt(FROZEN_DELTA_MIN_PP)
        & delta_pp.le(FROZEN_DELTA_MAX_PP)
        & neutral.notna()
        & applied.notna()
        & actual.notna()
    )
    out = out.loc[weak_band].copy()
    if out.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    delta_pp = delta_pp.loc[weak_band]
    adjustment = adjustment.loc[weak_band]
    neutral = neutral.loc[weak_band]
    applied = applied.loc[weak_band]
    actual = actual.loc[weak_band]

    neutralized = neutral
    applied_abs = (applied - actual).abs()
    neutralized_abs = (neutralized - actual).abs()

    out["Weak_Reduce_Eligible"] = True
    out["Neutralized_Projection"] = neutralized
    out["Applied_Absolute_Error"] = applied_abs
    out["Neutralized_Absolute_Error"] = neutralized_abs
    out["Applied_Error"] = applied - actual
    out["Neutralized_Error"] = neutralized - actual
    out["Neutralized_Win_vs_Applied"] = neutralized_abs.lt(applied_abs)
    out["Applied_Win_vs_Neutralized"] = applied_abs.lt(neutralized_abs)
    out["Neutralized_Applied_Tie"] = np.isclose(neutralized_abs, applied_abs)

    dates = pd.to_datetime(out.get("game_date"), errors="coerce")
    oos = dates.gt(pd.Timestamp(DERIVATION_CUTOFF_DATE))
    out["Evidence_Lane"] = np.where(oos, "FORWARD_OOS", "DERIVATION_BACKTEST")
    out["Counts_For_Promotion"] = oos
    out["Report_Only"] = REPORT_ONLY
    out["Production_Authority"] = PRODUCTION_AUTHORITY
    out["Validation_Version"] = VERSION

    for column in DETAIL_COLUMNS:
        if column not in out.columns:
            out[column] = np.nan
    return out[DETAIL_COLUMNS].reset_index(drop=True)


def _empty_metrics() -> dict[str, object]:
    return {
        "Starts": 0,
        "Observed_Days": 0,
        "Distinct_Opponents": 0,
        "Applied_MAE": np.nan,
        "Neutralized_MAE": np.nan,
        "Neutralized_Relative_MAE_vs_Applied": np.nan,
        "Neutralized_Win_Share_vs_Applied": np.nan,
        "Applied_Win_Share_vs_Neutralized": np.nan,
        "Tie_Share": np.nan,
        "Applied_Bias": np.nan,
        "Neutralized_Bias": np.nan,
        "Neutralized_Bias_Abs_Change_vs_Applied": np.nan,
        "Mean_Original_Reduction_K": np.nan,
        "Mean_Opponent_K_Delta_PP": np.nan,
    }


def _metrics(group: pd.DataFrame) -> dict[str, object]:
    if group is None or group.empty:
        return _empty_metrics()

    applied_mae = float(_num(group, "Applied_Absolute_Error").mean())
    neutralized_mae = float(_num(group, "Neutralized_Absolute_Error").mean())
    applied_bias = float(_num(group, "Applied_Error").mean())
    neutralized_bias = float(_num(group, "Neutralized_Error").mean())
    relative = np.nan if applied_mae <= 0 else float((applied_mae - neutralized_mae) / applied_mae)

    return {
        "Starts": int(len(group)),
        "Observed_Days": int(group["game_date"].dropna().astype(str).nunique()),
        "Distinct_Opponents": int(group["opponent"].dropna().astype(str).nunique()),
        "Applied_MAE": applied_mae,
        "Neutralized_MAE": neutralized_mae,
        "Neutralized_Relative_MAE_vs_Applied": relative,
        "Neutralized_Win_Share_vs_Applied": float(group["Neutralized_Win_vs_Applied"].astype(bool).mean()),
        "Applied_Win_Share_vs_Neutralized": float(group["Applied_Win_vs_Neutralized"].astype(bool).mean()),
        "Tie_Share": float(group["Neutralized_Applied_Tie"].astype(bool).mean()),
        "Applied_Bias": applied_bias,
        "Neutralized_Bias": neutralized_bias,
        "Neutralized_Bias_Abs_Change_vs_Applied": float(abs(neutralized_bias) - abs(applied_bias)),
        "Mean_Original_Reduction_K": float(_num(group, "Reduction_Magnitude_K").mean()),
        "Mean_Opponent_K_Delta_PP": float(_num(group, "Opponent_K_Delta_PP").mean()),
    }


def _status(lane: str, metrics: dict[str, object]) -> tuple[str, str, str]:
    if lane == "DERIVATION_BACKTEST":
        return (
            "DESCRIPTIVE_ONLY",
            "These weak suppressive rows motivated the frozen neutralization hypothesis and cannot validate it.",
            "FREEZE_HYPOTHESIS_AND_COLLECT_FORWARD_EVIDENCE",
        )

    n = int(metrics["Starts"])
    days = int(metrics["Observed_Days"])
    opponents = int(metrics["Distinct_Opponents"])
    if n < MIN_OOS_STARTS or days < MIN_OOS_DAYS or opponents < MIN_OOS_OPPONENTS:
        return (
            "LEARNING",
            f"Need {MIN_OOS_STARTS} forward OOS starts, {MIN_OOS_DAYS} days, and {MIN_OOS_OPPONENTS} opponents; have {n}, {days}, and {opponents}.",
            "KEEP_WEAK_REDUCE_NEUTRALIZATION_FROZEN_AND_LEARN",
        )

    rel = metrics["Neutralized_Relative_MAE_vs_Applied"]
    wins = metrics["Neutralized_Win_Share_vs_Applied"]
    bias_change = metrics["Neutralized_Bias_Abs_Change_vs_Applied"]
    if pd.notna(rel) and pd.notna(wins) and pd.notna(bias_change):
        if (
            float(rel) >= MIN_SUPPORT_RELATIVE_MAE
            and float(wins) >= MIN_SUPPORT_WIN_SHARE
            and float(bias_change) <= BIAS_WORSEN_TOLERANCE
        ):
            return (
                "SUPPORTED",
                "Frozen weak-REDUCE neutralization clears forward MAE, head-to-head, and bias guardrails versus the live applied weak reduction.",
                "MANUAL_PROMOTION_REVIEW_ONLY",
            )
        if float(rel) < 0.0 and float(wins) < 0.50:
            return (
                "HURTING",
                "Frozen weak-REDUCE neutralization worsens forward MAE and loses head-to-head versus the live applied weak reduction.",
                "REJECT_NEUTRALIZATION_KEEP_PRODUCTION_UNCHANGED",
            )

    return (
        "MIXED",
        "Forward sample clears size/diversity gates but does not clearly support or reject weak-REDUCE neutralization.",
        "KEEP_PRODUCTION_UNCHANGED_PENDING_MANUAL_REVIEW",
    )


def summarize(detail: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for lane in ("DERIVATION_BACKTEST", "FORWARD_OOS"):
        group = detail.loc[detail["Evidence_Lane"].eq(lane)].copy() if not detail.empty else pd.DataFrame()
        metrics = _metrics(group)
        status, reason, action = _status(lane, metrics)
        rows.append({
            "Evidence_Lane": lane,
            "Evidence_Status": status,
            **metrics,
            "Frozen_Delta_Min_PP": FROZEN_DELTA_MIN_PP,
            "Frozen_Delta_Max_PP": FROZEN_DELTA_MAX_PP,
            "Derivation_Cutoff_Date": DERIVATION_CUTOFF_DATE,
            "Reason": reason,
            "Recommended_Action": action,
            "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "Validation_Version": VERSION,
        })
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-only frozen weak-REDUCE neutralization shadow")
    parser.add_argument("--source", type=Path, default=Path("data/opponent_matchup_reduce_stress_detail.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/opponent_matchup_weak_reduce_neutral_shadow_detail.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/opponent_matchup_weak_reduce_neutral_shadow_summary.csv"))
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f"Missing source detail: {args.source}")
    detail = build_detail(pd.read_csv(args.source))
    summary = summarize(detail)
    args.detail.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.detail, index=False)
    summary.to_csv(args.summary, index=False)
    print(summary.to_string(index=False))
    print(
        "report_only="
        f"{REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY} "
        f"frozen_delta_band=({FROZEN_DELTA_MIN_PP},{FROZEN_DELTA_MAX_PP}]"
    )


if __name__ == "__main__":
    main()
