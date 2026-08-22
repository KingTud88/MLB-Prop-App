from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from training.projection_underperformer_shadow import (
    VERSION as SHADOW_VERSION,
    build_detail as build_shadow_detail,
)

VERSION = "projection-underperformer-forward-challenger-v1-preregistered-report-only"
PREREGISTRATION_VERSION = "projection-underperformer-forward-preregistration-v1"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_PROJECTION_ADJUSTMENT = True
NO_AUTO_PROMOTION = True
AUTOMATIC_DECISION_ALLOWED = False
SUPPORTING_DIAGNOSTIC_ONLY = True
PROMOTION_ROW_REGISTERED = False

PREREGISTERED_GAME_DATE = "2026-08-22"
FIRST_ELIGIBLE_GAME_DATE = "2026-08-23"
MIN_GLOBAL_RESOLVED_STARTS = 60
MIN_GLOBAL_RESOLVED_DAYS = 10
MIN_GLOBAL_PITCHERS = 20
MIN_RULE_STARTS = 15
UNDERINDEX_RESIDUAL_LIFT = -0.50
OVERINDEX_RESIDUAL_LIFT = 0.50

RULES = (
    {
        "Rule_ID": "CONFIDENCE_MEDIUM",
        "Rule_Definition": "Confidence == MEDIUM",
        "Rule_Field": "Confidence",
        "Rule_Operator": "EQ",
        "Rule_Value": "MEDIUM",
        "Flag_Column": "Flag_Confidence_MEDIUM",
        "Historical_Resolved_Starts": 35,
        "Historical_Residual_Lift": -0.7210022413336374,
    },
    {
        "Rule_ID": "DATA_QUALITY_LT50",
        "Rule_Definition": "numeric Data_Quality < 50",
        "Rule_Field": "Data_Quality",
        "Rule_Operator": "LT",
        "Rule_Value": "50",
        "Flag_Column": "Flag_Data_Quality_LT50",
        "Historical_Resolved_Starts": 16,
        "Historical_Residual_Lift": -0.7328345612382103,
    },
    {
        "Rule_ID": "LEASH_TIGHT",
        "Rule_Definition": "Leash_Label == TIGHT",
        "Rule_Field": "Leash_Label",
        "Rule_Operator": "EQ",
        "Rule_Value": "TIGHT",
        "Flag_Column": "Flag_Leash_TIGHT",
        "Historical_Resolved_Starts": 77,
        "Historical_Residual_Lift": -0.588076249239811,
    },
)

PREREGISTRATION_COLUMNS = [
    "Preregistration_Version",
    "Preregistered_Game_Date",
    "First_Eligible_Game_Date",
    "Rule_ID",
    "Rule_Definition",
    "Rule_Field",
    "Rule_Operator",
    "Rule_Value",
    "Historical_Source",
    "Historical_Source_Version",
    "Historical_Signal",
    "Historical_Resolved_Starts",
    "Historical_Residual_Lift",
    "Primary_Outcome",
    "Primary_Effect",
    "Rule_Min_Starts",
    "Global_Min_Starts",
    "Global_Min_Days",
    "Global_Min_Pitchers",
    "Underindex_Residual_Lift_Threshold",
    "Selection_Basis",
    "Report_Only",
    "Production_Authority",
    "No_Projection_Adjustment",
    "No_Auto_Promotion",
    "Automatic_Decision_Allowed",
    "Supporting_Diagnostic_Only",
    "Promotion_Row_Registered",
]

FORWARD_DETAIL_COLUMNS = [
    "Game_Date",
    "Pitcher",
    "Pitcher_ID",
    "Team",
    "Opponent",
    "Projection",
    "Actual_K",
    "K_Residual",
    "Below_Projection",
    "Material_Underperform_Event",
    "Confidence",
    "Data_Quality",
    "Leash_Label",
    "Flag_Confidence_MEDIUM",
    "Flag_Data_Quality_LT50",
    "Flag_Leash_TIGHT",
    "Any_Preregistered_Risk_Flag",
    "Report_Only",
    "Production_Authority",
    "No_Projection_Adjustment",
    "Forward_Evaluation_Version",
]

EVALUATION_COLUMNS = [
    "Rule_ID",
    "Rule_Definition",
    "Historical_Reference_Starts",
    "Historical_Reference_Residual_Lift",
    "Future_Resolved_Starts",
    "Future_Resolved_Days",
    "Future_Distinct_Pitchers",
    "Required_Global_Starts",
    "Required_Global_Days",
    "Required_Global_Pitchers",
    "Flagged_Starts",
    "Required_Flagged_Starts",
    "Flagged_Days",
    "Flagged_Pitchers",
    "Flag_Rate",
    "Flagged_Below_Projection_Rate",
    "Flagged_Material_Underperform_Rate",
    "Flagged_Mean_K_Residual",
    "Future_Overall_Mean_K_Residual",
    "Residual_Lift_vs_Future_Overall",
    "Signal",
    "Ready_For_Manual_Review",
    "Status",
    "Recommended_Action",
    "First_Eligible_Game_Date",
    "Report_Only",
    "Production_Authority",
    "No_Projection_Adjustment",
    "No_Auto_Promotion",
    "Automatic_Decision_Allowed",
    "Supporting_Diagnostic_Only",
    "Promotion_Row_Registered",
    "Evaluation_Version",
]

SUMMARY_COLUMNS = [
    "Status",
    "Future_Resolved_Starts",
    "Required_Global_Starts",
    "Future_Resolved_Days",
    "Required_Global_Days",
    "Future_Distinct_Pitchers",
    "Required_Global_Pitchers",
    "Rules_Preregistered",
    "Rules_With_Min_Starts",
    "Rules_Ready_For_Manual_Review",
    "Underindex_Rules",
    "Recommended_Action",
    "Preregistered_Game_Date",
    "First_Eligible_Game_Date",
    "Report_Only",
    "Production_Authority",
    "No_Projection_Adjustment",
    "No_Auto_Promotion",
    "Automatic_Decision_Allowed",
    "Supporting_Diagnostic_Only",
    "Promotion_Row_Registered",
    "Evaluation_Version",
]


def _text(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.upper()


def build_preregistration() -> pd.DataFrame:
    rows = []
    for rule in RULES:
        rows.append(
            {
                "Preregistration_Version": PREREGISTRATION_VERSION,
                "Preregistered_Game_Date": PREREGISTERED_GAME_DATE,
                "First_Eligible_Game_Date": FIRST_ELIGIBLE_GAME_DATE,
                "Rule_ID": rule["Rule_ID"],
                "Rule_Definition": rule["Rule_Definition"],
                "Rule_Field": rule["Rule_Field"],
                "Rule_Operator": rule["Rule_Operator"],
                "Rule_Value": rule["Rule_Value"],
                "Historical_Source": "data/projection_underperformer_shadow_cohorts.csv",
                "Historical_Source_Version": SHADOW_VERSION,
                "Historical_Signal": "UNDERINDEX",
                "Historical_Resolved_Starts": rule["Historical_Resolved_Starts"],
                "Historical_Residual_Lift": rule["Historical_Residual_Lift"],
                "Primary_Outcome": "exact frozen-projection K residual",
                "Primary_Effect": "Residual_Lift_vs_Future_Overall",
                "Rule_Min_Starts": MIN_RULE_STARTS,
                "Global_Min_Starts": MIN_GLOBAL_RESOLVED_STARTS,
                "Global_Min_Days": MIN_GLOBAL_RESOLVED_DAYS,
                "Global_Min_Pitchers": MIN_GLOBAL_PITCHERS,
                "Underindex_Residual_Lift_Threshold": UNDERINDEX_RESIDUAL_LIFT,
                "Selection_Basis": (
                    "Only mature UNDERINDEX cohorts in the human-reviewed 10-day "
                    "Projection Underperformer Shadow sample; no composite rule is promotion-eligible."
                ),
                "Report_Only": REPORT_ONLY,
                "Production_Authority": PRODUCTION_AUTHORITY,
                "No_Projection_Adjustment": NO_PROJECTION_ADJUSTMENT,
                "No_Auto_Promotion": NO_AUTO_PROMOTION,
                "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
                "Supporting_Diagnostic_Only": SUPPORTING_DIAGNOSTIC_ONLY,
                "Promotion_Row_Registered": PROMOTION_ROW_REGISTERED,
            }
        )
    return pd.DataFrame(rows, columns=PREREGISTRATION_COLUMNS)


def build_forward_detail(history: pd.DataFrame) -> pd.DataFrame:
    shadow = build_shadow_detail(history)
    if shadow.empty:
        return pd.DataFrame(columns=FORWARD_DETAIL_COLUMNS)

    dates = pd.to_datetime(shadow["Game_Date"], errors="coerce")
    eligible = shadow.loc[
        dates.notna() & dates.ge(pd.Timestamp(FIRST_ELIGIBLE_GAME_DATE))
    ].copy()
    if eligible.empty:
        return pd.DataFrame(columns=FORWARD_DETAIL_COLUMNS)

    eligible["Flag_Confidence_MEDIUM"] = _text(eligible["Confidence"]).eq("MEDIUM")
    quality = pd.to_numeric(eligible["Data_Quality"], errors="coerce")
    eligible["Flag_Data_Quality_LT50"] = quality.notna() & quality.lt(50.0)
    eligible["Flag_Leash_TIGHT"] = _text(eligible["Leash_Label"]).eq("TIGHT")
    eligible["Any_Preregistered_Risk_Flag"] = eligible[
        ["Flag_Confidence_MEDIUM", "Flag_Data_Quality_LT50", "Flag_Leash_TIGHT"]
    ].any(axis=1)
    eligible["Forward_Evaluation_Version"] = VERSION
    return eligible[FORWARD_DETAIL_COLUMNS].reset_index(drop=True)


def _signal(flagged_starts: int, lift: float) -> str:
    if flagged_starts < MIN_RULE_STARTS or not np.isfinite(lift):
        return "LEARNING"
    if lift <= UNDERINDEX_RESIDUAL_LIFT:
        return "UNDERINDEX"
    if lift >= OVERINDEX_RESIDUAL_LIFT:
        return "OVERINDEX"
    return "NEUTRAL"


def build_evaluation(detail: pd.DataFrame) -> pd.DataFrame:
    frame = detail.copy() if detail is not None else pd.DataFrame(columns=FORWARD_DETAIL_COLUMNS)
    future_starts = int(len(frame))
    dates = pd.to_datetime(frame.get("Game_Date"), errors="coerce")
    future_days = int(dates.dropna().dt.date.nunique()) if future_starts else 0
    future_pitchers = (
        int(frame.get("Pitcher", pd.Series(dtype=object)).dropna().astype(str).nunique())
        if future_starts
        else 0
    )
    residual = (
        pd.to_numeric(frame.get("K_Residual"), errors="coerce")
        if future_starts
        else pd.Series(dtype=float)
    )
    overall_mean = float(residual.mean()) if residual.notna().any() else np.nan
    global_mature = (
        future_starts >= MIN_GLOBAL_RESOLVED_STARTS
        and future_days >= MIN_GLOBAL_RESOLVED_DAYS
        and future_pitchers >= MIN_GLOBAL_PITCHERS
    )

    rows = []
    for rule in RULES:
        flag_column = rule["Flag_Column"]
        mask = (
            frame.get(flag_column, pd.Series(False, index=frame.index))
            .fillna(False)
            .astype(bool)
        )
        flagged = frame.loc[mask].copy()
        flagged_starts = int(len(flagged))
        flagged_dates = pd.to_datetime(flagged.get("Game_Date"), errors="coerce")
        flagged_days = int(flagged_dates.dropna().dt.date.nunique()) if flagged_starts else 0
        flagged_pitchers = (
            int(flagged.get("Pitcher", pd.Series(dtype=object)).dropna().astype(str).nunique())
            if flagged_starts
            else 0
        )
        flagged_residual = (
            pd.to_numeric(flagged.get("K_Residual"), errors="coerce")
            if flagged_starts
            else pd.Series(dtype=float)
        )
        flagged_mean = (
            float(flagged_residual.mean()) if flagged_residual.notna().any() else np.nan
        )
        lift = (
            float(flagged_mean - overall_mean)
            if np.isfinite(flagged_mean) and np.isfinite(overall_mean)
            else np.nan
        )
        ready = bool(global_mature and flagged_starts >= MIN_RULE_STARTS)
        status = (
            "WAITING_FOR_FUTURE_DATA"
            if future_starts == 0
            else "READY_FOR_MANUAL_RESEARCH_REVIEW"
            if ready
            else "LEARNING"
        )
        rows.append(
            {
                "Rule_ID": rule["Rule_ID"],
                "Rule_Definition": rule["Rule_Definition"],
                "Historical_Reference_Starts": rule["Historical_Resolved_Starts"],
                "Historical_Reference_Residual_Lift": rule["Historical_Residual_Lift"],
                "Future_Resolved_Starts": future_starts,
                "Future_Resolved_Days": future_days,
                "Future_Distinct_Pitchers": future_pitchers,
                "Required_Global_Starts": MIN_GLOBAL_RESOLVED_STARTS,
                "Required_Global_Days": MIN_GLOBAL_RESOLVED_DAYS,
                "Required_Global_Pitchers": MIN_GLOBAL_PITCHERS,
                "Flagged_Starts": flagged_starts,
                "Required_Flagged_Starts": MIN_RULE_STARTS,
                "Flagged_Days": flagged_days,
                "Flagged_Pitchers": flagged_pitchers,
                "Flag_Rate": float(flagged_starts / future_starts) if future_starts else np.nan,
                "Flagged_Below_Projection_Rate": (
                    float(flagged["Below_Projection"].astype(bool).mean())
                    if flagged_starts
                    else np.nan
                ),
                "Flagged_Material_Underperform_Rate": (
                    float(flagged["Material_Underperform_Event"].astype(bool).mean())
                    if flagged_starts
                    else np.nan
                ),
                "Flagged_Mean_K_Residual": flagged_mean,
                "Future_Overall_Mean_K_Residual": overall_mean,
                "Residual_Lift_vs_Future_Overall": lift,
                "Signal": _signal(flagged_starts, lift),
                "Ready_For_Manual_Review": ready,
                "Status": status,
                "Recommended_Action": (
                    "MANUAL_REVIEW_FROZEN_FORWARD_SIGNAL_ONLY_NO_PRODUCTION_CHANGE"
                    if ready
                    else "COLLECT_FUTURE_ONLY_EVIDENCE"
                ),
                "First_Eligible_Game_Date": FIRST_ELIGIBLE_GAME_DATE,
                "Report_Only": REPORT_ONLY,
                "Production_Authority": PRODUCTION_AUTHORITY,
                "No_Projection_Adjustment": NO_PROJECTION_ADJUSTMENT,
                "No_Auto_Promotion": NO_AUTO_PROMOTION,
                "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
                "Supporting_Diagnostic_Only": SUPPORTING_DIAGNOSTIC_ONLY,
                "Promotion_Row_Registered": PROMOTION_ROW_REGISTERED,
                "Evaluation_Version": VERSION,
            }
        )
    return pd.DataFrame(rows, columns=EVALUATION_COLUMNS)


def build_summary(detail: pd.DataFrame, evaluation: pd.DataFrame) -> pd.DataFrame:
    frame = detail.copy() if detail is not None else pd.DataFrame(columns=FORWARD_DETAIL_COLUMNS)
    eval_frame = (
        evaluation.copy() if evaluation is not None else pd.DataFrame(columns=EVALUATION_COLUMNS)
    )
    future_starts = int(len(frame))
    dates = pd.to_datetime(frame.get("Game_Date"), errors="coerce")
    future_days = int(dates.dropna().dt.date.nunique()) if future_starts else 0
    future_pitchers = (
        int(frame.get("Pitcher", pd.Series(dtype=object)).dropna().astype(str).nunique())
        if future_starts
        else 0
    )
    rules_with_min = (
        int(pd.to_numeric(eval_frame.get("Flagged_Starts"), errors="coerce").ge(MIN_RULE_STARTS).sum())
        if not eval_frame.empty
        else 0
    )
    ready_rules = (
        int(eval_frame.get("Ready_For_Manual_Review", pd.Series(dtype=bool)).fillna(False).astype(bool).sum())
        if not eval_frame.empty
        else 0
    )
    underindex_rules = (
        int(eval_frame.get("Signal", pd.Series(dtype=object)).astype(str).eq("UNDERINDEX").sum())
        if not eval_frame.empty
        else 0
    )

    if future_starts == 0:
        status = "WAITING_FOR_FUTURE_DATA"
    elif ready_rules:
        status = "READY_FOR_MANUAL_RESEARCH_REVIEW"
    else:
        status = "LEARNING"

    return pd.DataFrame(
        [
            {
                "Status": status,
                "Future_Resolved_Starts": future_starts,
                "Required_Global_Starts": MIN_GLOBAL_RESOLVED_STARTS,
                "Future_Resolved_Days": future_days,
                "Required_Global_Days": MIN_GLOBAL_RESOLVED_DAYS,
                "Future_Distinct_Pitchers": future_pitchers,
                "Required_Global_Pitchers": MIN_GLOBAL_PITCHERS,
                "Rules_Preregistered": len(RULES),
                "Rules_With_Min_Starts": rules_with_min,
                "Rules_Ready_For_Manual_Review": ready_rules,
                "Underindex_Rules": underindex_rules,
                "Recommended_Action": (
                    "MANUAL_REVIEW_ONLY_NO_PRODUCTION_CHANGE"
                    if ready_rules
                    else "COLLECT_FUTURE_ONLY_EVIDENCE"
                ),
                "Preregistered_Game_Date": PREREGISTERED_GAME_DATE,
                "First_Eligible_Game_Date": FIRST_ELIGIBLE_GAME_DATE,
                "Report_Only": REPORT_ONLY,
                "Production_Authority": PRODUCTION_AUTHORITY,
                "No_Projection_Adjustment": NO_PROJECTION_ADJUSTMENT,
                "No_Auto_Promotion": NO_AUTO_PROMOTION,
                "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
                "Supporting_Diagnostic_Only": SUPPORTING_DIAGNOSTIC_ONLY,
                "Promotion_Row_Registered": PROMOTION_ROW_REGISTERED,
                "Evaluation_Version": VERSION,
            }
        ],
        columns=SUMMARY_COLUMNS,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate the frozen future-only Projection Underperformer challenger protocol."
    )
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument(
        "--preregistration",
        type=Path,
        default=Path("data/projection_underperformer_forward_preregistration.csv"),
    )
    parser.add_argument(
        "--detail",
        type=Path,
        default=Path("data/projection_underperformer_forward_detail.csv"),
    )
    parser.add_argument(
        "--evaluation",
        type=Path,
        default=Path("data/projection_underperformer_forward_evaluation.csv"),
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("data/projection_underperformer_forward_summary.csv"),
    )
    args = parser.parse_args()

    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    preregistration = build_preregistration()
    detail = build_forward_detail(history)
    evaluation = build_evaluation(detail)
    summary = build_summary(detail, evaluation)

    for frame, path in (
        (preregistration, args.preregistration),
        (detail, args.detail),
        (evaluation, args.evaluation),
        (summary, args.summary),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)

    print(summary.to_string(index=False))
    print(evaluation.to_string(index=False))


if __name__ == "__main__":
    main()
