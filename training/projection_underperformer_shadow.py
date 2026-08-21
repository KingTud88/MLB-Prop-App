from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from training.projection_crusher_shadow import build_detail as build_residual_detail

VERSION = "projection-underperformer-shadow-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_PROJECTION_ADJUSTMENT = True
MIN_RESOLVED_STARTS = 60
MIN_RESOLVED_DAYS = 10
MIN_PITCHERS = 20
MIN_COHORT_STARTS = 8

DETAIL_COLUMNS = [
    "Game_Date", "Pitcher", "Pitcher_ID", "Team", "Opponent",
    "Projection", "Actual_K", "K_Residual", "Below_Projection", "Material_Underperform_Event",
    "Confidence", "Data_Quality", "Opponent_K_Pct", "Lineup_State", "Starter_Role", "Leash_Label",
    "SIM_Mean_K", "MATH_Mean_K", "SIM_MATH_Disagreement", "Projection_SD",
    "Report_Only", "Production_Authority", "No_Projection_Adjustment", "Research_Version",
]


def _quality_bucket(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "UNKNOWN"
    number = float(number)
    if number >= 90:
        return "90-100"
    if number >= 75:
        return "75-89"
    if number >= 50:
        return "50-74"
    return "<50"


def _opponent_bucket(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "UNKNOWN"
    number = float(number)
    if number <= 1.0:
        number *= 100.0
    if number >= 25.0:
        return "HIGH_K_25+"
    if number >= 22.0:
        return "MID_K_22-24.9"
    return "LOW_K_<22"


def _projection_bucket(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "UNKNOWN"
    number = float(number)
    if number < 4.5:
        return "<4.5"
    if number < 5.5:
        return "4.5-5.49"
    if number < 6.5:
        return "5.5-6.49"
    return "6.5+"


def _disagreement_bucket(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "UNKNOWN"
    number = abs(float(number))
    if number < 0.25:
        return "<0.25 K"
    if number < 0.50:
        return "0.25-0.49 K"
    if number < 1.00:
        return "0.50-0.99 K"
    return "1.00+ K"


def _pitcher_status(starts: int, below_rate: float, mean_residual: float) -> str:
    if starts < 3:
        return "LEARNING"
    if below_rate >= (2.0 / 3.0) and mean_residual < -0.5:
        return "UNDERPERFORMER"
    if below_rate >= 0.55 and mean_residual < 0.0:
        return "BELOW_PROJECTION"
    return "MIXED"


def build_detail(history: pd.DataFrame) -> pd.DataFrame:
    base = build_residual_detail(history)
    if base.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)
    detail = base.copy()
    residual = pd.to_numeric(detail["K_Residual"], errors="coerce")
    detail["Below_Projection"] = residual.lt(0.0)
    detail["Material_Underperform_Event"] = residual.le(-2.0)
    detail["Report_Only"] = REPORT_ONLY
    detail["Production_Authority"] = PRODUCTION_AUTHORITY
    detail["No_Projection_Adjustment"] = NO_PROJECTION_ADJUSTMENT
    detail["Research_Version"] = VERSION
    return detail[DETAIL_COLUMNS].reset_index(drop=True)


def build_pitcher_summary(detail: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Pitcher", "Resolved_Starts", "Below_Projection_Count", "Below_Projection_Rate",
        "Mean_K_Residual", "Median_K_Residual", "Material_Underperform_Events", "Material_Underperform_Rate",
        "Underperformer_Status", "Report_Only", "Production_Authority", "Research_Version",
    ]
    if detail is None or detail.empty:
        return pd.DataFrame(columns=columns)
    rows = []
    for pitcher, group in detail.groupby("Pitcher", dropna=False):
        residual = pd.to_numeric(group["K_Residual"], errors="coerce")
        below = group["Below_Projection"].astype(bool)
        material = group["Material_Underperform_Event"].astype(bool)
        starts = int(len(group))
        below_rate = float(below.mean())
        mean_residual = float(residual.mean())
        rows.append({
            "Pitcher": str(pitcher),
            "Resolved_Starts": starts,
            "Below_Projection_Count": int(below.sum()),
            "Below_Projection_Rate": below_rate,
            "Mean_K_Residual": mean_residual,
            "Median_K_Residual": float(residual.median()),
            "Material_Underperform_Events": int(material.sum()),
            "Material_Underperform_Rate": float(material.mean()),
            "Underperformer_Status": _pitcher_status(starts, below_rate, mean_residual),
            "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "Research_Version": VERSION,
        })
    status_rank = {"UNDERPERFORMER": 0, "BELOW_PROJECTION": 1, "LEARNING": 2, "MIXED": 3}
    report = pd.DataFrame(rows, columns=columns)
    report["_status_rank"] = report["Underperformer_Status"].map(status_rank).fillna(9)
    return report.sort_values(
        ["_status_rank", "Below_Projection_Rate", "Mean_K_Residual", "Resolved_Starts"],
        ascending=[True, False, True, False],
    ).drop(columns=["_status_rank"]).reset_index(drop=True)


def build_cohort_summary(detail: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Dimension", "Cohort", "Resolved_Starts", "Below_Projection_Rate", "Material_Underperform_Rate",
        "Mean_K_Residual", "Residual_Lift_vs_Overall", "Signal", "Report_Only",
        "Production_Authority", "Research_Version",
    ]
    if detail is None or detail.empty:
        return pd.DataFrame(columns=columns)
    frame = detail.copy()
    frame["Projection_Bucket"] = frame["Projection"].map(_projection_bucket)
    frame["Quality_Bucket"] = frame["Data_Quality"].map(_quality_bucket)
    frame["Opponent_K_Bucket"] = frame["Opponent_K_Pct"].map(_opponent_bucket)
    frame["SIM_MATH_Disagreement_Bucket"] = frame["SIM_MATH_Disagreement"].map(_disagreement_bucket)
    overall = float(pd.to_numeric(frame["K_Residual"], errors="coerce").mean())
    specs = (
        ("Projection", "Projection_Bucket"),
        ("Confidence", "Confidence"),
        ("Data Quality", "Quality_Bucket"),
        ("Opponent K Environment", "Opponent_K_Bucket"),
        ("SIM/MATH Disagreement", "SIM_MATH_Disagreement_Bucket"),
        ("Lineup State", "Lineup_State"),
        ("Starter Role", "Starter_Role"),
        ("Leash", "Leash_Label"),
    )
    rows = []
    for dimension, col in specs:
        for cohort, group in frame.groupby(col, dropna=False):
            n = int(len(group))
            if n < MIN_COHORT_STARTS:
                continue
            mean_residual = float(pd.to_numeric(group["K_Residual"], errors="coerce").mean())
            lift = mean_residual - overall
            signal = "LEARNING"
            if n >= 15:
                if lift <= -0.50:
                    signal = "UNDERINDEX"
                elif lift >= 0.50:
                    signal = "OVERINDEX"
                else:
                    signal = "NEUTRAL"
            rows.append({
                "Dimension": dimension,
                "Cohort": str(cohort),
                "Resolved_Starts": n,
                "Below_Projection_Rate": float(group["Below_Projection"].astype(bool).mean()),
                "Material_Underperform_Rate": float(group["Material_Underperform_Event"].astype(bool).mean()),
                "Mean_K_Residual": mean_residual,
                "Residual_Lift_vs_Overall": lift,
                "Signal": signal,
                "Report_Only": REPORT_ONLY,
                "Production_Authority": PRODUCTION_AUTHORITY,
                "Research_Version": VERSION,
            })
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns).sort_values(
        ["Dimension", "Residual_Lift_vs_Overall", "Resolved_Starts"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def build_gate(detail: pd.DataFrame, cohorts: pd.DataFrame | None = None) -> pd.DataFrame:
    resolved = int(len(detail)) if detail is not None else 0
    dates = pd.to_datetime(detail.get("Game_Date"), errors="coerce").dropna() if resolved else pd.Series(dtype="datetime64[ns]")
    days = int(dates.dt.date.nunique()) if not dates.empty else 0
    pitchers = int(detail.get("Pitcher", pd.Series(dtype=object)).nunique()) if resolved else 0
    below_rate = float(detail["Below_Projection"].astype(bool).mean()) if resolved else np.nan
    material_rate = float(detail["Material_Underperform_Event"].astype(bool).mean()) if resolved else np.nan
    mean_residual = float(pd.to_numeric(detail["K_Residual"], errors="coerce").mean()) if resolved else np.nan
    mature = resolved >= MIN_RESOLVED_STARTS and days >= MIN_RESOLVED_DAYS and pitchers >= MIN_PITCHERS
    status = "READY_FOR_MANUAL_RESEARCH_REVIEW" if mature else "LEARNING"
    remaining = []
    if resolved < MIN_RESOLVED_STARTS:
        remaining.append(f"starts {resolved}/{MIN_RESOLVED_STARTS}")
    if days < MIN_RESOLVED_DAYS:
        remaining.append(f"days {days}/{MIN_RESOLVED_DAYS}")
    if pitchers < MIN_PITCHERS:
        remaining.append(f"pitchers {pitchers}/{MIN_PITCHERS}")
    reason = (
        "Maturity reached for manual review of whether a negative-residual predictor should be frozen for future-only evaluation. No projection adjustment is authorized."
        if mature else
        "Need " + ", ".join(remaining) + " before freezing any underperformer-aware challenger."
    )
    return pd.DataFrame([{
        "Status": status,
        "Resolved_Starts": resolved,
        "Required_Starts": MIN_RESOLVED_STARTS,
        "Resolved_Days": days,
        "Required_Days": MIN_RESOLVED_DAYS,
        "Distinct_Pitchers": pitchers,
        "Required_Pitchers": MIN_PITCHERS,
        "Below_Projection_Rate": below_rate,
        "Material_Underperform_Rate": material_rate,
        "Mean_K_Residual": mean_residual,
        "Cohorts_Tracked": int(len(cohorts)) if cohorts is not None else 0,
        "Ready_For_Manual_Review": mature,
        "Recommended_Action": "MANUAL_RESEARCH_REVIEW_THEN_FREEZE_FORWARD_CHALLENGER" if mature else "COLLECT_EXACT_PROJECTION_UNDERPERFORMER_EVIDENCE",
        "Reason": reason,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "No_Projection_Adjustment": NO_PROJECTION_ADJUSTMENT,
        "Research_Version": VERSION,
    }])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build report-only exact-projection underperformer shadow research.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/projection_underperformer_shadow_detail.csv"))
    parser.add_argument("--pitchers", type=Path, default=Path("data/projection_underperformer_shadow_pitchers.csv"))
    parser.add_argument("--cohorts", type=Path, default=Path("data/projection_underperformer_shadow_cohorts.csv"))
    parser.add_argument("--gate", type=Path, default=Path("data/projection_underperformer_shadow_gate.csv"))
    args = parser.parse_args()
    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    detail = build_detail(history)
    pitchers = build_pitcher_summary(detail)
    cohorts = build_cohort_summary(detail)
    gate = build_gate(detail, cohorts)
    for frame, path in ((detail, args.detail), (pitchers, args.pitchers), (cohorts, args.cohorts), (gate, args.gate)):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    print(gate.to_string(index=False))


if __name__ == "__main__":
    main()
