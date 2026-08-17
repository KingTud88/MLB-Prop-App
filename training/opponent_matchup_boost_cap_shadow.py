from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "opponent-matchup-boost-cap-shadow-v1"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
FROZEN_CAP_K = 0.10
DERIVATION_CUTOFF_DATE = "2026-08-16"
MIN_OOS_STARTS = 30
MIN_OOS_DAYS = 10
MIN_OOS_OPPONENTS = 12
MIN_SUPPORT_RELATIVE_MAE = 0.005
MIN_SUPPORT_WIN_SHARE = 0.52
BIAS_WORSEN_TOLERANCE = 0.05

DETAIL_COLUMNS = [
    "game_date", "game_pk", "pitcher_id", "player", "team", "opponent",
    "Opponent_K_Rate", "Opponent_K_Delta_PP", "Matchup_PA", "Lineup_State",
    "Data_Quality", "Quality_Band", "Neutral_Opponent_Projection",
    "Applied_Projection", "Matchup_Adjustment_K", "Actual_Strikeouts",
    "Cap_K", "Capped_Adjustment_K", "Cap_Was_Binding", "Capped_Projection",
    "Applied_Absolute_Error", "Capped_Absolute_Error", "Neutral_Absolute_Error",
    "Applied_Error", "Capped_Error", "Neutral_Error", "Capped_Win_vs_Applied",
    "Applied_Win_vs_Capped", "Capped_Applied_Tie", "Capped_Win_vs_Neutral",
    "Neutral_Win_vs_Capped", "Capped_Neutral_Tie", "Evidence_Lane",
    "Counts_For_Promotion", "Report_Only", "Production_Authority", "Validation_Version",
]
SUMMARY_COLUMNS = [
    "Evidence_Lane", "Evidence_Status", "Starts", "Observed_Days", "Distinct_Opponents",
    "Binding_Starts", "Binding_Rate", "Applied_MAE", "Capped_MAE", "Neutral_MAE",
    "Capped_Relative_MAE_vs_Applied", "Capped_Relative_MAE_vs_Neutral",
    "Capped_Win_Share_vs_Applied", "Applied_Win_Share_vs_Capped",
    "Capped_Applied_Tie_Share", "Capped_Win_Share_vs_Neutral",
    "Neutral_Win_Share_vs_Capped", "Capped_Neutral_Tie_Share", "Applied_Bias",
    "Capped_Bias", "Neutral_Bias", "Capped_Bias_Abs_Change_vs_Applied",
    "Mean_Applied_Boost_K", "Mean_Capped_Boost_K", "Frozen_Cap_K",
    "Derivation_Cutoff_Date", "Reason", "Recommended_Action", "Report_Only",
    "Production_Authority", "Validation_Version",
]


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def build_detail(boost_detail: pd.DataFrame) -> pd.DataFrame:
    if boost_detail is None or boost_detail.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)
    out = boost_detail.copy()
    adjustment = _num(out, "Matchup_Adjustment_K")
    neutral = _num(out, "Neutral_Opponent_Projection")
    applied = _num(out, "Applied_Projection")
    actual = _num(out, "Actual_Strikeouts")
    valid = adjustment.gt(0.0) & neutral.notna() & applied.notna() & actual.notna()
    out = out.loc[valid].copy()
    adjustment = adjustment.loc[valid]
    neutral = neutral.loc[valid]
    applied = applied.loc[valid]
    actual = actual.loc[valid]

    capped_adjustment = adjustment.clip(upper=FROZEN_CAP_K)
    capped = neutral + capped_adjustment
    applied_abs = (applied - actual).abs()
    neutral_abs = (neutral - actual).abs()

    out["Cap_K"] = FROZEN_CAP_K
    out["Capped_Adjustment_K"] = capped_adjustment
    out["Cap_Was_Binding"] = adjustment.gt(FROZEN_CAP_K)
    out["Capped_Projection"] = capped
    out["Applied_Absolute_Error"] = applied_abs
    out["Capped_Absolute_Error"] = (capped - actual).abs()
    out["Neutral_Absolute_Error"] = neutral_abs
    out["Applied_Error"] = applied - actual
    out["Capped_Error"] = capped - actual
    out["Neutral_Error"] = neutral - actual
    out["Capped_Win_vs_Applied"] = out["Capped_Absolute_Error"].lt(applied_abs)
    out["Applied_Win_vs_Capped"] = applied_abs.lt(out["Capped_Absolute_Error"])
    out["Capped_Applied_Tie"] = np.isclose(out["Capped_Absolute_Error"], applied_abs)
    out["Capped_Win_vs_Neutral"] = out["Capped_Absolute_Error"].lt(neutral_abs)
    out["Neutral_Win_vs_Capped"] = neutral_abs.lt(out["Capped_Absolute_Error"])
    out["Capped_Neutral_Tie"] = np.isclose(out["Capped_Absolute_Error"], neutral_abs)

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


def _metrics(group: pd.DataFrame) -> dict[str, object]:
    if group is None or group.empty:
        return {key: np.nan for key in SUMMARY_COLUMNS if key not in {
            "Evidence_Lane", "Evidence_Status", "Frozen_Cap_K", "Derivation_Cutoff_Date",
            "Reason", "Recommended_Action", "Report_Only", "Production_Authority", "Validation_Version"
        }} | {"Starts": 0, "Observed_Days": 0, "Distinct_Opponents": 0, "Binding_Starts": 0}

    applied_mae = float(_num(group, "Applied_Absolute_Error").mean())
    capped_mae = float(_num(group, "Capped_Absolute_Error").mean())
    neutral_mae = float(_num(group, "Neutral_Absolute_Error").mean())
    applied_bias = float(_num(group, "Applied_Error").mean())
    capped_bias = float(_num(group, "Capped_Error").mean())
    neutral_bias = float(_num(group, "Neutral_Error").mean())
    return {
        "Starts": int(len(group)),
        "Observed_Days": int(group["game_date"].dropna().astype(str).nunique()),
        "Distinct_Opponents": int(group["opponent"].dropna().astype(str).nunique()),
        "Binding_Starts": int(group["Cap_Was_Binding"].fillna(False).astype(bool).sum()),
        "Binding_Rate": float(group["Cap_Was_Binding"].fillna(False).astype(bool).mean()),
        "Applied_MAE": applied_mae,
        "Capped_MAE": capped_mae,
        "Neutral_MAE": neutral_mae,
        "Capped_Relative_MAE_vs_Applied": np.nan if applied_mae <= 0 else float((applied_mae - capped_mae) / applied_mae),
        "Capped_Relative_MAE_vs_Neutral": np.nan if neutral_mae <= 0 else float((neutral_mae - capped_mae) / neutral_mae),
        "Capped_Win_Share_vs_Applied": float(group["Capped_Win_vs_Applied"].astype(bool).mean()),
        "Applied_Win_Share_vs_Capped": float(group["Applied_Win_vs_Capped"].astype(bool).mean()),
        "Capped_Applied_Tie_Share": float(group["Capped_Applied_Tie"].astype(bool).mean()),
        "Capped_Win_Share_vs_Neutral": float(group["Capped_Win_vs_Neutral"].astype(bool).mean()),
        "Neutral_Win_Share_vs_Capped": float(group["Neutral_Win_vs_Capped"].astype(bool).mean()),
        "Capped_Neutral_Tie_Share": float(group["Capped_Neutral_Tie"].astype(bool).mean()),
        "Applied_Bias": applied_bias,
        "Capped_Bias": capped_bias,
        "Neutral_Bias": neutral_bias,
        "Capped_Bias_Abs_Change_vs_Applied": float(abs(capped_bias) - abs(applied_bias)),
        "Mean_Applied_Boost_K": float(_num(group, "Matchup_Adjustment_K").mean()),
        "Mean_Capped_Boost_K": float(_num(group, "Capped_Adjustment_K").mean()),
    }


def _status(lane: str, metrics: dict[str, object]) -> tuple[str, str, str]:
    if lane == "DERIVATION_BACKTEST":
        return "DESCRIPTIVE_ONLY", "These rows helped derive the +0.10 K shadow-cap hypothesis and cannot validate it.", "FREEZE_HYPOTHESIS_AND_COLLECT_FORWARD_EVIDENCE"
    n, days, opponents = int(metrics["Starts"]), int(metrics["Observed_Days"]), int(metrics["Distinct_Opponents"])
    if n < MIN_OOS_STARTS or days < MIN_OOS_DAYS or opponents < MIN_OOS_OPPONENTS:
        return "LEARNING", f"Need {MIN_OOS_STARTS} forward OOS starts, {MIN_OOS_DAYS} days, and {MIN_OOS_OPPONENTS} opponents; have {n}, {days}, and {opponents}.", "KEEP_SHADOW_CAP_FROZEN_AND_LEARN"
    rel = metrics["Capped_Relative_MAE_vs_Applied"]
    wins = metrics["Capped_Win_Share_vs_Applied"]
    bias_change = metrics["Capped_Bias_Abs_Change_vs_Applied"]
    if pd.notna(rel) and pd.notna(wins) and pd.notna(bias_change):
        if float(rel) >= MIN_SUPPORT_RELATIVE_MAE and float(wins) >= MIN_SUPPORT_WIN_SHARE and float(bias_change) <= BIAS_WORSEN_TOLERANCE:
            return "SUPPORTED", "Frozen +0.10 K cap clears forward MAE, head-to-head, and bias guardrails versus live applied boosts.", "MANUAL_PROMOTION_REVIEW_ONLY"
        if float(rel) < 0.0 and float(wins) < 0.50:
            return "HURTING", "Frozen +0.10 K cap worsens forward MAE and loses head-to-head versus live applied boosts.", "REJECT_CAP_KEEP_PRODUCTION_UNCHANGED"
    return "MIXED", "Forward sample clears size/diversity gates but does not clearly support or reject the frozen cap.", "KEEP_PRODUCTION_UNCHANGED_PENDING_MANUAL_REVIEW"


def summarize(detail: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for lane in ("DERIVATION_BACKTEST", "FORWARD_OOS"):
        group = detail.loc[detail["Evidence_Lane"].eq(lane)].copy() if not detail.empty else pd.DataFrame()
        metrics = _metrics(group)
        status, reason, action = _status(lane, metrics)
        rows.append({
            "Evidence_Lane": lane, "Evidence_Status": status, **metrics,
            "Frozen_Cap_K": FROZEN_CAP_K, "Derivation_Cutoff_Date": DERIVATION_CUTOFF_DATE,
            "Reason": reason, "Recommended_Action": action, "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY, "Validation_Version": VERSION,
        })
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-only frozen +0.10 K opponent boost-cap shadow")
    parser.add_argument("--source", type=Path, default=Path("data/opponent_matchup_boost_stress_detail.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/opponent_matchup_boost_cap_shadow_detail.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/opponent_matchup_boost_cap_shadow_summary.csv"))
    args = parser.parse_args()
    if not args.source.exists():
        raise SystemExit(f"Missing source detail: {args.source}")
    detail = build_detail(pd.read_csv(args.source))
    summary = summarize(detail)
    args.detail.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.detail, index=False)
    summary.to_csv(args.summary, index=False)
    print(summary.to_string(index=False))
    print(f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY} frozen_cap_k={FROZEN_CAP_K}")


if __name__ == "__main__":
    main()
