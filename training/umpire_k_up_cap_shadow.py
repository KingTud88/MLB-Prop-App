from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "umpire-k-up-cap-shadow-v1-preregistered-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_PROJECTION_ADJUSTMENT = True
FROZEN_MAX_K_UP_FACTOR = 1.015
DERIVATION_CUTOFF_DATE = "2026-08-18"
MIN_FORWARD_CHANGED_STARTS = 30
MIN_FORWARD_DAYS = 10
MIN_FORWARD_UMPIRES = 12
MIN_SUPPORT_RELATIVE_MAE = 0.005
MIN_SUPPORT_WIN_SHARE = 0.52
BIAS_WORSEN_TOLERANCE = 0.05

DETAIL_COLUMNS = [
    "game_date", "game_pk", "pitcher_id", "player", "team", "opponent",
    "umpire_id", "umpire_name", "Base_Projection", "Candidate_Factor",
    "Candidate_Projection", "Actual_Strikeouts", "Capped_Factor",
    "Cap_Was_Binding", "Capped_Projection", "Base_Absolute_Error",
    "Incumbent_Absolute_Error", "Capped_Absolute_Error", "Base_Error",
    "Incumbent_Error", "Capped_Error", "Capped_Win_vs_Incumbent",
    "Incumbent_Win_vs_Capped", "Capped_Incumbent_Tie",
    "Incumbent_Overprediction", "Capped_Overprediction", "Evidence_Lane",
    "Counts_For_Promotion", "Report_Only", "Production_Authority",
    "No_Projection_Adjustment", "Validation_Version",
]

SUMMARY_COLUMNS = [
    "Evidence_Lane", "Evidence_Status", "Eligible_Starts", "Changed_Starts",
    "Observed_Days", "Distinct_Umpires", "Base_MAE", "Incumbent_MAE",
    "Capped_MAE", "Capped_Relative_MAE_vs_Incumbent",
    "Capped_Win_Share_vs_Incumbent", "Incumbent_Win_Share_vs_Capped",
    "Capped_Incumbent_Tie_Share", "Incumbent_Bias", "Capped_Bias",
    "Capped_Bias_Abs_Change_vs_Incumbent", "Incumbent_Overprediction_Rate",
    "Capped_Overprediction_Rate", "Overprediction_Rate_Change",
    "Mean_Incumbent_Factor", "Mean_Capped_Factor", "Frozen_Max_K_Up_Factor",
    "Derivation_Cutoff_Date", "Reason", "Recommended_Action",
    "Manual_Review_Ready", "Report_Only", "Production_Authority",
    "No_Projection_Adjustment", "Validation_Version",
]


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _truthy(frame: pd.DataFrame, column: str) -> pd.Series:
    raw = frame.get(column, pd.Series(False, index=frame.index))
    return raw.fillna(False).astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def build_detail(umpire_detail: pd.DataFrame) -> pd.DataFrame:
    """Build a frozen K-UP-only cap challenger from authentic umpire validation rows.

    The challenger caps only positive umpire factors above +1.5%. K-DOWN rows and
    smaller positive adjustments are carried through unchanged. The lane is
    report-only and cannot affect production projection values.
    """
    if umpire_detail is None or umpire_detail.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    source = umpire_detail.copy()
    eligible = _truthy(source, "OOS_Eligible")
    base = _num(source, "Base_Projection")
    incumbent = _num(source, "Candidate_Projection")
    factor = _num(source, "Candidate_Factor")
    actual = _num(source, "Actual_Strikeouts")
    valid = eligible & base.notna() & incumbent.notna() & factor.notna() & actual.notna()
    out = source.loc[valid].copy()
    if out.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    base = base.loc[valid]
    incumbent = incumbent.loc[valid]
    factor = factor.loc[valid]
    actual = actual.loc[valid]

    capped_factor = factor.where(factor.le(FROZEN_MAX_K_UP_FACTOR), FROZEN_MAX_K_UP_FACTOR)
    capped_projection = base * capped_factor
    cap_binding = factor.gt(FROZEN_MAX_K_UP_FACTOR)

    base_abs = (base - actual).abs()
    incumbent_abs = (incumbent - actual).abs()
    capped_abs = (capped_projection - actual).abs()
    incumbent_error = incumbent - actual
    capped_error = capped_projection - actual

    out["Capped_Factor"] = capped_factor
    out["Cap_Was_Binding"] = cap_binding
    out["Capped_Projection"] = capped_projection
    out["Base_Absolute_Error"] = base_abs
    out["Incumbent_Absolute_Error"] = incumbent_abs
    out["Capped_Absolute_Error"] = capped_abs
    out["Base_Error"] = base - actual
    out["Incumbent_Error"] = incumbent_error
    out["Capped_Error"] = capped_error
    out["Capped_Win_vs_Incumbent"] = capped_abs.lt(incumbent_abs)
    out["Incumbent_Win_vs_Capped"] = incumbent_abs.lt(capped_abs)
    out["Capped_Incumbent_Tie"] = np.isclose(capped_abs, incumbent_abs)
    out["Incumbent_Overprediction"] = incumbent_error.gt(0.0)
    out["Capped_Overprediction"] = capped_error.gt(0.0)

    dates = pd.to_datetime(out.get("game_date"), errors="coerce")
    forward = dates.gt(pd.Timestamp(DERIVATION_CUTOFF_DATE))
    out["Evidence_Lane"] = np.where(forward, "FORWARD_OOS", "DERIVATION_BACKTEST")
    out["Counts_For_Promotion"] = forward & cap_binding
    out["Report_Only"] = REPORT_ONLY
    out["Production_Authority"] = PRODUCTION_AUTHORITY
    out["No_Projection_Adjustment"] = NO_PROJECTION_ADJUSTMENT
    out["Validation_Version"] = VERSION

    for column in DETAIL_COLUMNS:
        if column not in out.columns:
            out[column] = np.nan
    return out[DETAIL_COLUMNS].reset_index(drop=True)


def _metrics(eligible_group: pd.DataFrame) -> dict[str, object]:
    if eligible_group is None or eligible_group.empty:
        return {
            "Eligible_Starts": 0,
            "Changed_Starts": 0,
            "Observed_Days": 0,
            "Distinct_Umpires": 0,
            "Base_MAE": np.nan,
            "Incumbent_MAE": np.nan,
            "Capped_MAE": np.nan,
            "Capped_Relative_MAE_vs_Incumbent": np.nan,
            "Capped_Win_Share_vs_Incumbent": np.nan,
            "Incumbent_Win_Share_vs_Capped": np.nan,
            "Capped_Incumbent_Tie_Share": np.nan,
            "Incumbent_Bias": np.nan,
            "Capped_Bias": np.nan,
            "Capped_Bias_Abs_Change_vs_Incumbent": np.nan,
            "Incumbent_Overprediction_Rate": np.nan,
            "Capped_Overprediction_Rate": np.nan,
            "Overprediction_Rate_Change": np.nan,
            "Mean_Incumbent_Factor": np.nan,
            "Mean_Capped_Factor": np.nan,
        }

    changed = eligible_group.loc[eligible_group["Cap_Was_Binding"].fillna(False).astype(bool)].copy()
    if changed.empty:
        metrics = _metrics(pd.DataFrame())
        metrics["Eligible_Starts"] = int(len(eligible_group))
        return metrics

    incumbent_mae = float(_num(changed, "Incumbent_Absolute_Error").mean())
    capped_mae = float(_num(changed, "Capped_Absolute_Error").mean())
    base_mae = float(_num(changed, "Base_Absolute_Error").mean())
    incumbent_bias = float(_num(changed, "Incumbent_Error").mean())
    capped_bias = float(_num(changed, "Capped_Error").mean())
    incumbent_over = float(_truthy(changed, "Incumbent_Overprediction").mean())
    capped_over = float(_truthy(changed, "Capped_Overprediction").mean())

    return {
        "Eligible_Starts": int(len(eligible_group)),
        "Changed_Starts": int(len(changed)),
        "Observed_Days": int(changed["game_date"].replace("", np.nan).dropna().astype(str).nunique()),
        "Distinct_Umpires": int(_num(changed, "umpire_id").dropna().astype(int).nunique()),
        "Base_MAE": base_mae,
        "Incumbent_MAE": incumbent_mae,
        "Capped_MAE": capped_mae,
        "Capped_Relative_MAE_vs_Incumbent": (
            np.nan if incumbent_mae <= 0 else float((incumbent_mae - capped_mae) / incumbent_mae)
        ),
        "Capped_Win_Share_vs_Incumbent": float(_truthy(changed, "Capped_Win_vs_Incumbent").mean()),
        "Incumbent_Win_Share_vs_Capped": float(_truthy(changed, "Incumbent_Win_vs_Capped").mean()),
        "Capped_Incumbent_Tie_Share": float(_truthy(changed, "Capped_Incumbent_Tie").mean()),
        "Incumbent_Bias": incumbent_bias,
        "Capped_Bias": capped_bias,
        "Capped_Bias_Abs_Change_vs_Incumbent": float(abs(capped_bias) - abs(incumbent_bias)),
        "Incumbent_Overprediction_Rate": incumbent_over,
        "Capped_Overprediction_Rate": capped_over,
        "Overprediction_Rate_Change": float(capped_over - incumbent_over),
        "Mean_Incumbent_Factor": float(_num(changed, "Candidate_Factor").mean()),
        "Mean_Capped_Factor": float(_num(changed, "Capped_Factor").mean()),
    }


def _status(lane: str, metrics: dict[str, object]) -> tuple[str, str, str, bool]:
    if lane == "DERIVATION_BACKTEST":
        return (
            "DESCRIPTIVE_ONLY",
            "Rows on or before 2026-08-18 helped derive the frozen +1.5% K-UP cap hypothesis and cannot validate it.",
            "FREEZE_HYPOTHESIS_AND_COLLECT_FORWARD_EVIDENCE",
            False,
        )

    starts = int(metrics["Changed_Starts"])
    days = int(metrics["Observed_Days"])
    umpires = int(metrics["Distinct_Umpires"])
    if starts < MIN_FORWARD_CHANGED_STARTS or days < MIN_FORWARD_DAYS or umpires < MIN_FORWARD_UMPIRES:
        return (
            "LEARNING",
            f"Need {MIN_FORWARD_CHANGED_STARTS} forward changed starts, {MIN_FORWARD_DAYS} days, and "
            f"{MIN_FORWARD_UMPIRES} umpires; have {starts}, {days}, and {umpires}.",
            "KEEP_K_UP_CAP_SHADOW_FROZEN_AND_LEARN",
            False,
        )

    rel = metrics["Capped_Relative_MAE_vs_Incumbent"]
    wins = metrics["Capped_Win_Share_vs_Incumbent"]
    bias_change = metrics["Capped_Bias_Abs_Change_vs_Incumbent"]
    if pd.notna(rel) and pd.notna(wins) and pd.notna(bias_change):
        if (
            float(rel) >= MIN_SUPPORT_RELATIVE_MAE
            and float(wins) >= MIN_SUPPORT_WIN_SHARE
            and float(bias_change) <= BIAS_WORSEN_TOLERANCE
        ):
            return (
                "SUPPORTED",
                "Frozen +1.5% K-UP cap clears forward MAE, head-to-head, and absolute-bias guardrails versus the incumbent umpire candidate.",
                "MANUAL_RESEARCH_REVIEW_ONLY",
                True,
            )
        if float(rel) < 0.0 and float(wins) < 0.50:
            return (
                "HURTING",
                "Frozen +1.5% K-UP cap worsens forward MAE and loses head-to-head versus the incumbent umpire candidate.",
                "REJECT_SHADOW_KEEP_UMPIRE_RESEARCH_UNCHANGED",
                True,
            )
    return (
        "MIXED",
        "Forward changed sample clears size and diversity gates but does not clearly support or reject the frozen K-UP cap.",
        "KEEP_UMPIRE_RESEARCH_UNCHANGED_PENDING_MANUAL_REVIEW",
        True,
    )


def summarize(detail: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for lane in ("DERIVATION_BACKTEST", "FORWARD_OOS"):
        group = (
            detail.loc[detail["Evidence_Lane"].eq(lane)].copy()
            if detail is not None and not detail.empty
            else pd.DataFrame(columns=DETAIL_COLUMNS)
        )
        metrics = _metrics(group)
        status, reason, action, review_ready = _status(lane, metrics)
        rows.append({
            "Evidence_Lane": lane,
            "Evidence_Status": status,
            **metrics,
            "Frozen_Max_K_Up_Factor": FROZEN_MAX_K_UP_FACTOR,
            "Derivation_Cutoff_Date": DERIVATION_CUTOFF_DATE,
            "Reason": reason,
            "Recommended_Action": action,
            "Manual_Review_Ready": review_ready,
            "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "No_Projection_Adjustment": NO_PROJECTION_ADJUSTMENT,
            "Validation_Version": VERSION,
        })
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-only frozen +1.5% K-UP umpire cap shadow")
    parser.add_argument("--source", type=Path, default=Path("data/umpire_k_live_validation_detail.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/umpire_k_up_cap_shadow_detail.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/umpire_k_up_cap_shadow_summary.csv"))
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
        f"report_only={REPORT_ONLY} production_authority={PRODUCTION_AUTHORITY} "
        f"frozen_max_k_up_factor={FROZEN_MAX_K_UP_FACTOR} cutoff={DERIVATION_CUTOFF_DATE}"
    )


if __name__ == "__main__":
    main()
