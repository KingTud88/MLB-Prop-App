from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from engine.starter_history import HISTORY_SEMANTICS

VERSION = "projection-crusher-shadow-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_PROJECTION_ADJUSTMENT = True
MIN_RESOLVED_STARTS = 60
MIN_RESOLVED_DAYS = 10
MIN_PITCHERS = 20
MIN_COHORT_STARTS = 8

DETAIL_COLUMNS = [
    "Game_Date", "Pitcher", "Pitcher_ID", "Team", "Opponent",
    "Projection", "Actual_K", "K_Residual", "Beat_Projection", "Material_Crusher_Event",
    "Confidence", "Data_Quality", "Opponent_K_Pct", "Lineup_State", "Starter_Role", "Leash_Label",
    "SIM_Mean_K", "MATH_Mean_K", "SIM_MATH_Disagreement", "Projection_SD",
    "Report_Only", "Production_Authority", "No_Projection_Adjustment", "Research_Version",
]


def _num(series: object, index: pd.Index) -> pd.Series:
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce")
    return pd.Series(np.nan, index=index, dtype=float)


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "confirmed"}


def _lineup_state(value: object) -> str:
    return "CONFIRMED" if _truthy(value) else "PROJECTED_OR_UNKNOWN"


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


def build_detail(history: pd.DataFrame) -> pd.DataFrame:
    if history is None or history.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)
    frame = history.copy()
    if "history_semantics" in frame.columns:
        current = frame["history_semantics"].astype(str).eq(HISTORY_SEMANTICS)
        if current.any():
            frame = frame.loc[current].copy()

    frame["Projection"] = _num(frame.get("projection"), frame.index)
    frame["Actual_K"] = _num(frame.get("actual_strikeouts"), frame.index)
    frame = frame.loc[frame["Projection"].notna() & frame["Actual_K"].notna()].copy()
    if frame.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS)

    frame["K_Residual"] = frame["Actual_K"] - frame["Projection"]
    frame["Beat_Projection"] = frame["K_Residual"].gt(0.0)
    frame["Material_Crusher_Event"] = frame["K_Residual"].ge(2.0)
    frame["Game_Date"] = pd.to_datetime(frame.get("game_date"), errors="coerce").dt.date.astype(str)
    frame["Pitcher"] = frame.get("player", pd.Series("Unknown", index=frame.index)).fillna("Unknown").astype(str)
    frame["Pitcher_ID"] = frame.get("pitcher_id", pd.Series(pd.NA, index=frame.index))
    frame["Team"] = frame.get("team", pd.Series("", index=frame.index)).fillna("").astype(str)
    frame["Opponent"] = frame.get("opponent", pd.Series("", index=frame.index)).fillna("").astype(str)
    frame["Confidence"] = frame.get("confidence", pd.Series("UNKNOWN", index=frame.index)).fillna("UNKNOWN").astype(str).str.upper()
    frame["Data_Quality"] = _num(frame.get("data_quality"), frame.index)
    frame["Opponent_K_Pct"] = _num(frame.get("opponent_k_pct"), frame.index)
    frame["Lineup_State"] = frame.get("lineup_confirmed", pd.Series(False, index=frame.index)).map(_lineup_state)
    frame["Starter_Role"] = frame.get("starter_role_label", pd.Series("UNKNOWN", index=frame.index)).fillna("UNKNOWN").astype(str).str.upper()
    frame["Leash_Label"] = frame.get("leash_label", pd.Series("UNKNOWN", index=frame.index)).fillna("UNKNOWN").astype(str).str.upper()
    frame["SIM_Mean_K"] = _num(frame.get("sim_mean_k"), frame.index)
    frame["MATH_Mean_K"] = _num(frame.get("math_mean_k"), frame.index)
    frame["SIM_MATH_Disagreement"] = (frame["SIM_Mean_K"] - frame["MATH_Mean_K"]).abs()
    frame["Projection_SD"] = _num(frame.get("k_sd"), frame.index)
    frame["Report_Only"] = REPORT_ONLY
    frame["Production_Authority"] = PRODUCTION_AUTHORITY
    frame["No_Projection_Adjustment"] = NO_PROJECTION_ADJUSTMENT
    frame["Research_Version"] = VERSION
    return frame[DETAIL_COLUMNS].reset_index(drop=True)


def build_pitcher_summary(detail: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Pitcher", "Resolved_Starts", "Beat_Projection_Count", "Beat_Projection_Rate",
        "Mean_K_Residual", "Median_K_Residual", "Material_Crusher_Events", "Material_Crusher_Rate",
        "Report_Only", "Production_Authority", "Research_Version",
    ]
    if detail is None or detail.empty:
        return pd.DataFrame(columns=columns)
    rows = []
    for pitcher, group in detail.groupby("Pitcher", dropna=False):
        residual = pd.to_numeric(group["K_Residual"], errors="coerce")
        rows.append({
            "Pitcher": str(pitcher),
            "Resolved_Starts": int(len(group)),
            "Beat_Projection_Count": int(group["Beat_Projection"].astype(bool).sum()),
            "Beat_Projection_Rate": float(group["Beat_Projection"].astype(bool).mean()),
            "Mean_K_Residual": float(residual.mean()),
            "Median_K_Residual": float(residual.median()),
            "Material_Crusher_Events": int(group["Material_Crusher_Event"].astype(bool).sum()),
            "Material_Crusher_Rate": float(group["Material_Crusher_Event"].astype(bool).mean()),
            "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "Research_Version": VERSION,
        })
    return pd.DataFrame(rows, columns=columns).sort_values(
        ["Beat_Projection_Rate", "Mean_K_Residual", "Resolved_Starts"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def build_cohort_summary(detail: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Dimension", "Cohort", "Resolved_Starts", "Beat_Projection_Rate", "Material_Crusher_Rate",
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
                if lift >= 0.50:
                    signal = "OVERINDEX"
                elif lift <= -0.50:
                    signal = "UNDERINDEX"
                else:
                    signal = "NEUTRAL"
            rows.append({
                "Dimension": dimension,
                "Cohort": str(cohort),
                "Resolved_Starts": n,
                "Beat_Projection_Rate": float(group["Beat_Projection"].astype(bool).mean()),
                "Material_Crusher_Rate": float(group["Material_Crusher_Event"].astype(bool).mean()),
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
        ascending=[True, False, False],
    ).reset_index(drop=True)


def build_gate(detail: pd.DataFrame, cohorts: pd.DataFrame | None = None) -> pd.DataFrame:
    resolved = int(len(detail)) if detail is not None else 0
    dates = pd.to_datetime(detail.get("Game_Date"), errors="coerce").dropna() if resolved else pd.Series(dtype="datetime64[ns]")
    days = int(dates.dt.date.nunique()) if not dates.empty else 0
    pitchers = int(detail.get("Pitcher", pd.Series(dtype=object)).nunique()) if resolved else 0
    crusher_rate = float(detail["Beat_Projection"].astype(bool).mean()) if resolved else np.nan
    material_rate = float(detail["Material_Crusher_Event"].astype(bool).mean()) if resolved else np.nan
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
        "Maturity reached for manual review of whether an exact-projection Crusher predictor should be frozen for future-only evaluation. No projection adjustment is authorized."
        if mature else
        "Need " + ", ".join(remaining) + " before freezing any Crusher-aware challenger."
    )
    return pd.DataFrame([{
        "Status": status,
        "Resolved_Starts": resolved,
        "Required_Starts": MIN_RESOLVED_STARTS,
        "Resolved_Days": days,
        "Required_Days": MIN_RESOLVED_DAYS,
        "Distinct_Pitchers": pitchers,
        "Required_Pitchers": MIN_PITCHERS,
        "Beat_Projection_Rate": crusher_rate,
        "Material_Crusher_Rate": material_rate,
        "Mean_K_Residual": mean_residual,
        "Cohorts_Tracked": int(len(cohorts)) if cohorts is not None else 0,
        "Ready_For_Manual_Review": mature,
        "Recommended_Action": "MANUAL_RESEARCH_REVIEW_THEN_FREEZE_FORWARD_CHALLENGER" if mature else "COLLECT_EXACT_PROJECTION_CRUSHER_EVIDENCE",
        "Reason": reason,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "No_Projection_Adjustment": NO_PROJECTION_ADJUSTMENT,
        "Research_Version": VERSION,
    }])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build report-only exact-projection Crusher shadow research.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/projection_crusher_shadow_detail.csv"))
    parser.add_argument("--pitchers", type=Path, default=Path("data/projection_crusher_shadow_pitchers.csv"))
    parser.add_argument("--cohorts", type=Path, default=Path("data/projection_crusher_shadow_cohorts.csv"))
    parser.add_argument("--gate", type=Path, default=Path("data/projection_crusher_shadow_gate.csv"))
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
