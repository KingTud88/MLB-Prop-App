from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from training.outs_opponent_pressure_capture import FIRST_ELIGIBLE_GAME_DATE
from training.outs_opponent_pressure_preregistration import (
    AUTOMATIC_DECISION_ALLOWED,
    HIGH_CONTACT_THRESHOLD,
    HIGH_OBP_THRESHOLD,
    MIN_GLOBAL_OPPONENTS,
    MIN_GLOBAL_PITCHERS,
    MIN_GLOBAL_RESOLVED_DAYS,
    MIN_GLOBAL_RESOLVED_STARTS,
    MIN_RULE_STARTS,
    MIN_SOURCE_COVERAGE,
    NO_AUTO_PROMOTION,
    NO_PROJECTION_ADJUSTMENT,
    OUTS_RESIDUAL_EFFECT_THRESHOLD,
    PREREGISTERED_GAME_DATE,
    PRODUCTION_AUTHORITY,
    PROMOTION_ROW_REGISTERED,
    REPORT_ONLY,
    RULES,
    SUPPORTING_DIAGNOSTIC_ONLY,
    build_preregistration,
)

VERSION = "outs-opponent-pressure-audit-v1-preregistered-report-only"

DETAIL_COLUMNS = [
    "Game_Date", "Game_PK", "Pitcher_ID", "Pitcher", "Team", "Opponent",
    "Frozen_Outs_Projection", "Actual_Outs", "Outs_Residual",
    "Opponent_K_Rate", "Opponent_Contact_Rate", "Opponent_OBP",
    "Lineup_Source", "Lineup_Confirmed", "Split_Coverage", "Context_Lineage",
    "Flag_OBP_HIGH_335_PLUS", "Flag_CONTACT_HIGH_800_PLUS",
    "Flag_OBP335_AND_CONTACT800", "Report_Only", "Production_Authority",
    "No_Projection_Adjustment", "Evaluation_Version",
]

EVALUATION_COLUMNS = [
    "Rule_ID", "Rule_Definition", "Expected_Direction", "Future_Resolved_Starts",
    "Future_Resolved_Days", "Future_Distinct_Pitchers", "Future_Distinct_Opponents",
    "Source_Coverage", "Required_Source_Coverage", "Flagged_Starts",
    "Required_Flagged_Starts", "Flagged_Days", "Flagged_Pitchers",
    "Flagged_Opponents", "Flag_Rate", "Flagged_Mean_Outs_Residual",
    "Unflagged_Mean_Outs_Residual", "Residual_Lift_vs_Unflagged",
    "Future_Overall_Mean_Outs_Residual", "Residual_Lift_vs_Future_Overall",
    "Signal", "Ready_For_Manual_Review", "Status", "Recommended_Action",
    "First_Eligible_Game_Date", "Report_Only", "Production_Authority",
    "No_Projection_Adjustment", "No_Auto_Promotion", "Automatic_Decision_Allowed",
    "Supporting_Diagnostic_Only", "Promotion_Row_Registered", "Evaluation_Version",
]

GATE_COLUMNS = [
    "Status", "Future_Eligible_Projection_Rows", "Future_Resolved_Starts",
    "Required_Global_Starts", "Future_Resolved_Days", "Required_Global_Days",
    "Future_Distinct_Pitchers", "Required_Global_Pitchers",
    "Future_Distinct_Opponents", "Required_Global_Opponents", "Source_Coverage",
    "Required_Source_Coverage", "Rules_Preregistered", "Rules_With_Min_Starts",
    "Rules_Ready_For_Manual_Review", "Recommended_Action", "Preregistered_Game_Date",
    "First_Eligible_Game_Date", "Report_Only", "Production_Authority",
    "No_Projection_Adjustment", "No_Auto_Promotion", "Automatic_Decision_Allowed",
    "Supporting_Diagnostic_Only", "Promotion_Row_Registered", "Evaluation_Version",
]


def _truthy(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def _best_context(context: pd.DataFrame) -> pd.DataFrame:
    if context is None or context.empty:
        return pd.DataFrame()
    frame = context.copy()
    frame["_eligible"] = _truthy(frame.get("audit_eligible", pd.Series(False, index=frame.index)))
    frame["_confirmed"] = _truthy(frame.get("lineup_confirmed", pd.Series(False, index=frame.index)))
    frame["_captured"] = pd.to_datetime(frame.get("pressure_captured_at_utc"), errors="coerce", utc=True)
    frame["_game_pk"] = pd.to_numeric(frame.get("game_pk"), errors="coerce")
    frame["_pitcher_id"] = pd.to_numeric(frame.get("pitcher_id"), errors="coerce")
    frame = frame.loc[frame["_game_pk"].notna() & frame["_pitcher_id"].notna()].copy()
    if frame.empty:
        return frame
    frame = frame.sort_values(["_game_pk", "_pitcher_id", "_eligible", "_confirmed", "_captured"])
    return frame.drop_duplicates(["_game_pk", "_pitcher_id"], keep="last")


def _eligible_projection_rows(projections: pd.DataFrame) -> pd.DataFrame:
    if projections is None or projections.empty:
        return pd.DataFrame()
    frame = projections.copy()
    dates = pd.to_datetime(frame.get("game_date"), errors="coerce")
    outs_projection = pd.to_numeric(frame.get("outs_projection"), errors="coerce")
    mask = dates.notna() & dates.ge(pd.Timestamp(FIRST_ELIGIBLE_GAME_DATE)) & outs_projection.notna()
    frame = frame.loc[mask].copy()
    if frame.empty:
        return frame
    frame["_game_pk"] = pd.to_numeric(frame.get("game_pk"), errors="coerce")
    frame["_pitcher_id"] = pd.to_numeric(frame.get("pitcher_id"), errors="coerce")
    frame = frame.loc[frame["_game_pk"].notna() & frame["_pitcher_id"].notna()].copy()
    return frame.drop_duplicates(["_game_pk", "_pitcher_id"], keep="last")


def build_detail(projections: pd.DataFrame, context: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float | int]]:
    eligible = _eligible_projection_rows(projections)
    eligible_count = int(len(eligible))
    if eligible.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS), {"eligible_projection_rows": 0, "source_coverage": np.nan}
    best = _best_context(context)
    if best.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS), {"eligible_projection_rows": eligible_count, "source_coverage": 0.0}
    merged = eligible.merge(best, on=["_game_pk", "_pitcher_id"], how="left", suffixes=("", "_ctx"))
    matched = _truthy(merged.get("audit_eligible", pd.Series(False, index=merged.index)))
    source_coverage = float(matched.mean())
    actual = pd.to_numeric(merged.get("actual_outs"), errors="coerce")
    projection = pd.to_numeric(merged.get("outs_projection"), errors="coerce")
    resolved = merged.loc[matched & actual.notna() & projection.notna()].copy()
    if resolved.empty:
        return pd.DataFrame(columns=DETAIL_COLUMNS), {"eligible_projection_rows": eligible_count, "source_coverage": source_coverage}

    resolved["Game_Date"] = pd.to_datetime(resolved["game_date"], errors="coerce").dt.date.astype(str)
    resolved["Game_PK"] = resolved["_game_pk"].astype(int)
    resolved["Pitcher_ID"] = resolved["_pitcher_id"].astype(int)
    resolved["Pitcher"] = resolved.get("player", pd.Series("", index=resolved.index)).fillna("").astype(str)
    resolved["Team"] = resolved.get("team", pd.Series("", index=resolved.index)).fillna("").astype(str)
    resolved["Opponent"] = resolved.get("opponent", pd.Series("", index=resolved.index)).fillna("").astype(str)
    resolved["Frozen_Outs_Projection"] = projection.loc[resolved.index]
    resolved["Actual_Outs"] = actual.loc[resolved.index]
    resolved["Outs_Residual"] = resolved["Actual_Outs"] - resolved["Frozen_Outs_Projection"]
    resolved["Opponent_K_Rate"] = pd.to_numeric(resolved.get("opponent_k_rate"), errors="coerce")
    resolved["Opponent_Contact_Rate"] = pd.to_numeric(resolved.get("opponent_contact_rate"), errors="coerce")
    resolved["Opponent_OBP"] = pd.to_numeric(resolved.get("opponent_obp"), errors="coerce")
    resolved["Lineup_Source"] = resolved.get("lineup_source", pd.Series("", index=resolved.index)).fillna("").astype(str)
    resolved["Lineup_Confirmed"] = _truthy(resolved.get("lineup_confirmed", pd.Series(False, index=resolved.index)))
    resolved["Split_Coverage"] = pd.to_numeric(resolved.get("split_coverage"), errors="coerce")
    resolved["Context_Lineage"] = resolved.get("lineage", pd.Series("", index=resolved.index)).fillna("").astype(str)
    resolved["Flag_OBP_HIGH_335_PLUS"] = resolved["Opponent_OBP"].ge(HIGH_OBP_THRESHOLD)
    resolved["Flag_CONTACT_HIGH_800_PLUS"] = resolved["Opponent_Contact_Rate"].ge(HIGH_CONTACT_THRESHOLD)
    resolved["Flag_OBP335_AND_CONTACT800"] = resolved["Flag_OBP_HIGH_335_PLUS"] & resolved["Flag_CONTACT_HIGH_800_PLUS"]
    resolved["Report_Only"] = REPORT_ONLY
    resolved["Production_Authority"] = PRODUCTION_AUTHORITY
    resolved["No_Projection_Adjustment"] = NO_PROJECTION_ADJUSTMENT
    resolved["Evaluation_Version"] = VERSION
    return resolved[DETAIL_COLUMNS].reset_index(drop=True), {"eligible_projection_rows": eligible_count, "source_coverage": source_coverage}


def _signal(flagged_starts: int, lift: float) -> str:
    if flagged_starts < MIN_RULE_STARTS or not np.isfinite(lift):
        return "LEARNING"
    if lift <= -OUTS_RESIDUAL_EFFECT_THRESHOLD:
        return "UNDERINDEX"
    if lift >= OUTS_RESIDUAL_EFFECT_THRESHOLD:
        return "OVERINDEX"
    return "NEUTRAL"


def build_evaluation(detail: pd.DataFrame, *, source_coverage: float) -> pd.DataFrame:
    resolved = int(len(detail)) if detail is not None else 0
    days = int(pd.to_datetime(detail.get("Game_Date"), errors="coerce").dt.date.nunique()) if resolved else 0
    pitchers = int(detail.get("Pitcher_ID", pd.Series(dtype=object)).nunique()) if resolved else 0
    opponents = int(detail.get("Opponent", pd.Series(dtype=object)).nunique()) if resolved else 0
    global_ready = resolved >= MIN_GLOBAL_RESOLVED_STARTS and days >= MIN_GLOBAL_RESOLVED_DAYS and pitchers >= MIN_GLOBAL_PITCHERS and opponents >= MIN_GLOBAL_OPPONENTS and np.isfinite(source_coverage) and source_coverage >= MIN_SOURCE_COVERAGE
    overall = float(pd.to_numeric(detail["Outs_Residual"], errors="coerce").mean()) if resolved else np.nan
    flag_columns = {
        "OBP_HIGH_335_PLUS": "Flag_OBP_HIGH_335_PLUS",
        "CONTACT_HIGH_800_PLUS": "Flag_CONTACT_HIGH_800_PLUS",
        "OBP335_AND_CONTACT800": "Flag_OBP335_AND_CONTACT800",
    }
    rows = []
    for rule_id, definition, _field, direction in RULES:
        flags = detail[flag_columns[rule_id]].astype(bool) if resolved else pd.Series(dtype=bool)
        flagged = detail.loc[flags] if resolved else pd.DataFrame(columns=detail.columns)
        unflagged = detail.loc[~flags] if resolved else pd.DataFrame(columns=detail.columns)
        n = int(len(flagged))
        flagged_mean = float(pd.to_numeric(flagged.get("Outs_Residual"), errors="coerce").mean()) if n else np.nan
        unflagged_mean = float(pd.to_numeric(unflagged.get("Outs_Residual"), errors="coerce").mean()) if len(unflagged) else np.nan
        lift_unflagged = flagged_mean - unflagged_mean if np.isfinite(flagged_mean) and np.isfinite(unflagged_mean) else np.nan
        lift_overall = flagged_mean - overall if np.isfinite(flagged_mean) and np.isfinite(overall) else np.nan
        ready = bool(global_ready and n >= MIN_RULE_STARTS)
        rows.append({
            "Rule_ID": rule_id, "Rule_Definition": definition, "Expected_Direction": direction,
            "Future_Resolved_Starts": resolved, "Future_Resolved_Days": days,
            "Future_Distinct_Pitchers": pitchers, "Future_Distinct_Opponents": opponents,
            "Source_Coverage": source_coverage, "Required_Source_Coverage": MIN_SOURCE_COVERAGE,
            "Flagged_Starts": n, "Required_Flagged_Starts": MIN_RULE_STARTS,
            "Flagged_Days": int(pd.to_datetime(flagged.get("Game_Date"), errors="coerce").dt.date.nunique()) if n else 0,
            "Flagged_Pitchers": int(flagged.get("Pitcher_ID", pd.Series(dtype=object)).nunique()) if n else 0,
            "Flagged_Opponents": int(flagged.get("Opponent", pd.Series(dtype=object)).nunique()) if n else 0,
            "Flag_Rate": float(n / resolved) if resolved else np.nan,
            "Flagged_Mean_Outs_Residual": flagged_mean,
            "Unflagged_Mean_Outs_Residual": unflagged_mean,
            "Residual_Lift_vs_Unflagged": lift_unflagged,
            "Future_Overall_Mean_Outs_Residual": overall,
            "Residual_Lift_vs_Future_Overall": lift_overall,
            "Signal": _signal(n, lift_unflagged),
            "Ready_For_Manual_Review": ready,
            "Status": "READY_FOR_MANUAL_RESEARCH_REVIEW" if ready else "LEARNING",
            "Recommended_Action": "MANUAL_RESEARCH_REVIEW_ONLY" if ready else "COLLECT_FUTURE_ONLY_EVIDENCE",
            "First_Eligible_Game_Date": FIRST_ELIGIBLE_GAME_DATE,
            "Report_Only": REPORT_ONLY, "Production_Authority": PRODUCTION_AUTHORITY,
            "No_Projection_Adjustment": NO_PROJECTION_ADJUSTMENT, "No_Auto_Promotion": NO_AUTO_PROMOTION,
            "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
            "Supporting_Diagnostic_Only": SUPPORTING_DIAGNOSTIC_ONLY,
            "Promotion_Row_Registered": PROMOTION_ROW_REGISTERED, "Evaluation_Version": VERSION,
        })
    return pd.DataFrame(rows, columns=EVALUATION_COLUMNS)


def build_gate(detail: pd.DataFrame, evaluation: pd.DataFrame, *, eligible_projection_rows: int, source_coverage: float) -> pd.DataFrame:
    resolved = int(len(detail)) if detail is not None else 0
    days = int(pd.to_datetime(detail.get("Game_Date"), errors="coerce").dt.date.nunique()) if resolved else 0
    pitchers = int(detail.get("Pitcher_ID", pd.Series(dtype=object)).nunique()) if resolved else 0
    opponents = int(detail.get("Opponent", pd.Series(dtype=object)).nunique()) if resolved else 0
    with_min = int(pd.to_numeric(evaluation.get("Flagged_Starts"), errors="coerce").ge(MIN_RULE_STARTS).sum()) if not evaluation.empty else 0
    ready_rules = int(_truthy(evaluation.get("Ready_For_Manual_Review", pd.Series(dtype=object))).sum()) if not evaluation.empty else 0
    if eligible_projection_rows == 0:
        status, action = "WAITING_FOR_FIRST_ELIGIBLE_GAME", "WAIT_FOR_2026_08_23_AND_CAPTURE_PREGAME_CONTEXT"
    elif not np.isfinite(source_coverage) or source_coverage < MIN_SOURCE_COVERAGE:
        status, action = "SOURCE_COVERAGE_BLOCKED", "RESTORE_PREGAME_PRESSURE_SOURCE_COVERAGE"
    elif ready_rules == len(RULES):
        status, action = "READY_FOR_MANUAL_RESEARCH_REVIEW", "MANUAL_RESEARCH_REVIEW_ONLY"
    else:
        status, action = "LEARNING", "COLLECT_FUTURE_ONLY_EVIDENCE"
    return pd.DataFrame([{
        "Status": status, "Future_Eligible_Projection_Rows": eligible_projection_rows,
        "Future_Resolved_Starts": resolved, "Required_Global_Starts": MIN_GLOBAL_RESOLVED_STARTS,
        "Future_Resolved_Days": days, "Required_Global_Days": MIN_GLOBAL_RESOLVED_DAYS,
        "Future_Distinct_Pitchers": pitchers, "Required_Global_Pitchers": MIN_GLOBAL_PITCHERS,
        "Future_Distinct_Opponents": opponents, "Required_Global_Opponents": MIN_GLOBAL_OPPONENTS,
        "Source_Coverage": source_coverage, "Required_Source_Coverage": MIN_SOURCE_COVERAGE,
        "Rules_Preregistered": len(RULES), "Rules_With_Min_Starts": with_min,
        "Rules_Ready_For_Manual_Review": ready_rules, "Recommended_Action": action,
        "Preregistered_Game_Date": PREREGISTERED_GAME_DATE, "First_Eligible_Game_Date": FIRST_ELIGIBLE_GAME_DATE,
        "Report_Only": REPORT_ONLY, "Production_Authority": PRODUCTION_AUTHORITY,
        "No_Projection_Adjustment": NO_PROJECTION_ADJUSTMENT, "No_Auto_Promotion": NO_AUTO_PROMOTION,
        "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
        "Supporting_Diagnostic_Only": SUPPORTING_DIAGNOSTIC_ONLY,
        "Promotion_Row_Registered": PROMOTION_ROW_REGISTERED, "Evaluation_Version": VERSION,
    }], columns=GATE_COLUMNS)


def write_outputs(root: Path) -> tuple[Path, Path, Path, Path]:
    root = Path(root)
    projection_path = root / "data" / "projection_log.csv"
    context_path = root / "data" / "outs_opponent_pressure_context_log.csv"
    projections = pd.read_csv(projection_path) if projection_path.exists() else pd.DataFrame()
    context = pd.read_csv(context_path) if context_path.exists() else pd.DataFrame()
    prereg = build_preregistration()
    detail, meta = build_detail(projections, context)
    coverage = float(meta["source_coverage"])
    evaluation = build_evaluation(detail, source_coverage=coverage)
    gate = build_gate(detail, evaluation, eligible_projection_rows=int(meta["eligible_projection_rows"]), source_coverage=coverage)
    paths = (
        root / "data" / "outs_opponent_pressure_preregistration.csv",
        root / "data" / "outs_opponent_pressure_detail.csv",
        root / "data" / "outs_opponent_pressure_summary.csv",
        root / "data" / "outs_opponent_pressure_gate.csv",
    )
    for frame, path in zip((prereg, detail, evaluation, gate), paths):
        frame.to_csv(path, index=False)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate future-only report-only opponent pressure for starter outs.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print("outs_opponent_pressure_outputs=" + ",".join(str(path) for path in write_outputs(args.root)))


if __name__ == "__main__":
    main()
