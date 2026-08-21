from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from engine.projection_crushers import bettable_k_target
from engine.starter_history import HISTORY_SEMANTICS

VERSION = "k-ladder-reliability-shadow-v1-report-only"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_PROJECTION_ADJUSTMENT = True
MIN_RESOLVED_CALLS = 60
MIN_RESOLVED_DAYS = 10
MIN_PITCHERS = 20
MIN_PROBABILITY_COVERAGE = 0.80
MIN_COHORT_CALLS = 8


def _num(series: object, index: pd.Index) -> pd.Series:
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce")
    return pd.Series(np.nan, index=index, dtype=float)


def _prob(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return None
    number = float(parsed)
    if 1.0 < number <= 100.0:
        number /= 100.0
    if not 0.0 <= number <= 1.0:
        return None
    return number


def _target_probability(row: pd.Series, target: int) -> float | None:
    values = [_prob(row.get(f"sim_{target}p")), _prob(row.get(f"math_{target}p"))]
    ready = [value for value in values if value is not None]
    return float(np.mean(ready)) if ready else None


def _headroom_bucket(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "UNKNOWN"
    number = float(number)
    if number < 0.25:
        return "0.00-0.24"
    if number < 0.50:
        return "0.25-0.49"
    if number < 0.75:
        return "0.50-0.74"
    return "0.75-0.99"


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


def build_detail(history: pd.DataFrame) -> pd.DataFrame:
    if history is None or history.empty:
        return pd.DataFrame()
    frame = history.copy()
    if "history_semantics" in frame.columns:
        current = frame["history_semantics"].astype(str).eq(HISTORY_SEMANTICS)
        if current.any():
            frame = frame.loc[current].copy()

    frame["Projection"] = _num(frame.get("projection"), frame.index)
    frame["Actual_K"] = _num(frame.get("actual_strikeouts"), frame.index)
    frame["K_Target"] = frame["Projection"].map(bettable_k_target)
    frame = frame.loc[frame["K_Target"].notna() & frame["Actual_K"].notna()].copy()
    if frame.empty:
        return pd.DataFrame()

    frame["K_Target"] = frame["K_Target"].astype(int)
    frame["Target_Label"] = frame["K_Target"].map(lambda value: f"{int(value)}+")
    frame["Projection_Headroom"] = frame["Projection"] - frame["K_Target"].astype(float)
    frame["Ladder_Win"] = frame["Actual_K"].ge(frame["K_Target"].astype(float))
    frame["Target_Probability"] = frame.apply(lambda row: _target_probability(row, int(row["K_Target"])), axis=1)
    frame["Brier"] = np.where(
        pd.to_numeric(frame["Target_Probability"], errors="coerce").notna(),
        (pd.to_numeric(frame["Target_Probability"], errors="coerce") - frame["Ladder_Win"].astype(float)) ** 2,
        np.nan,
    )
    frame["Game_Date"] = pd.to_datetime(frame.get("game_date"), errors="coerce").dt.date.astype(str)
    frame["Pitcher"] = frame.get("player", pd.Series("Unknown", index=frame.index)).fillna("Unknown").astype(str)
    frame["Pitcher_ID"] = frame.get("pitcher_id", pd.Series(pd.NA, index=frame.index))
    frame["Confidence"] = frame.get("confidence", pd.Series("UNKNOWN", index=frame.index)).fillna("UNKNOWN").astype(str).str.upper()
    frame["Data_Quality"] = _num(frame.get("data_quality"), frame.index)
    frame["Opponent_K_Pct"] = _num(frame.get("opponent_k_pct"), frame.index)
    frame["Headroom_Bucket"] = frame["Projection_Headroom"].map(_headroom_bucket)
    frame["Quality_Bucket"] = frame["Data_Quality"].map(_quality_bucket)
    frame["Opponent_K_Bucket"] = frame["Opponent_K_Pct"].map(_opponent_bucket)
    frame["Report_Only"] = REPORT_ONLY
    frame["Production_Authority"] = PRODUCTION_AUTHORITY
    frame["No_Projection_Adjustment"] = NO_PROJECTION_ADJUSTMENT
    frame["Research_Version"] = VERSION
    columns = [
        "Game_Date", "Pitcher", "Pitcher_ID", "Projection", "K_Target", "Target_Label",
        "Projection_Headroom", "Actual_K", "Ladder_Win", "Target_Probability", "Brier",
        "Confidence", "Data_Quality", "Opponent_K_Pct", "Headroom_Bucket", "Quality_Bucket",
        "Opponent_K_Bucket", "Report_Only", "Production_Authority", "No_Projection_Adjustment",
        "Research_Version",
    ]
    return frame[columns].reset_index(drop=True)


def build_cohort_summary(detail: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Dimension", "Cohort", "Resolved_Calls", "Ladder_Win_Rate", "Probability_Coverage",
        "Avg_Target_Probability", "Calibration_Gap", "Brier_Score", "Signal", "Report_Only",
        "Production_Authority", "Research_Version",
    ]
    if detail is None or detail.empty:
        return pd.DataFrame(columns=columns)
    rows = []
    for dimension, col in (
        ("Target", "Target_Label"),
        ("Projection Headroom", "Headroom_Bucket"),
        ("Confidence", "Confidence"),
        ("Data Quality", "Quality_Bucket"),
        ("Opponent K Environment", "Opponent_K_Bucket"),
    ):
        for cohort, group in detail.groupby(col, dropna=False):
            n = int(len(group))
            if n < MIN_COHORT_CALLS:
                continue
            prob = pd.to_numeric(group["Target_Probability"], errors="coerce")
            covered = prob.notna()
            hit_rate = float(group["Ladder_Win"].astype(bool).mean())
            avg_prob = float(prob[covered].mean()) if covered.any() else np.nan
            gap = avg_prob - hit_rate if covered.any() else np.nan
            brier = float(pd.to_numeric(group["Brier"], errors="coerce").mean()) if covered.any() else np.nan
            signal = "LEARNING"
            if n >= 15 and covered.mean() >= MIN_PROBABILITY_COVERAGE:
                signal = "CALIBRATION_WATCH" if abs(gap) >= 0.10 else "CALIBRATION_STABLE"
            rows.append({
                "Dimension": dimension,
                "Cohort": str(cohort),
                "Resolved_Calls": n,
                "Ladder_Win_Rate": hit_rate,
                "Probability_Coverage": float(covered.mean()),
                "Avg_Target_Probability": avg_prob,
                "Calibration_Gap": gap,
                "Brier_Score": brier,
                "Signal": signal,
                "Report_Only": REPORT_ONLY,
                "Production_Authority": PRODUCTION_AUTHORITY,
                "Research_Version": VERSION,
            })
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns).sort_values(
        ["Dimension", "Resolved_Calls"], ascending=[True, False]
    ).reset_index(drop=True)


def build_gate(detail: pd.DataFrame, cohorts: pd.DataFrame | None = None) -> pd.DataFrame:
    calls = int(len(detail)) if detail is not None else 0
    dates = pd.to_datetime(detail.get("Game_Date"), errors="coerce").dropna() if calls else pd.Series(dtype="datetime64[ns]")
    days = int(dates.dt.date.nunique()) if not dates.empty else 0
    pitchers = int(detail.get("Pitcher", pd.Series(dtype=object)).nunique()) if calls else 0
    probability = pd.to_numeric(detail.get("Target_Probability"), errors="coerce") if calls else pd.Series(dtype=float)
    coverage = float(probability.notna().mean()) if calls else 0.0
    hit_rate = float(detail["Ladder_Win"].astype(bool).mean()) if calls else np.nan
    avg_prob = float(probability.dropna().mean()) if probability.notna().any() else np.nan
    calibration_gap = avg_prob - hit_rate if probability.notna().any() else np.nan
    brier = float(pd.to_numeric(detail.get("Brier"), errors="coerce").mean()) if probability.notna().any() else np.nan
    mature = (
        calls >= MIN_RESOLVED_CALLS
        and days >= MIN_RESOLVED_DAYS
        and pitchers >= MIN_PITCHERS
        and coverage >= MIN_PROBABILITY_COVERAGE
    )
    status = "READY_FOR_MANUAL_RESEARCH_REVIEW" if mature else "LEARNING"
    blockers = []
    if calls < MIN_RESOLVED_CALLS:
        blockers.append(f"calls {calls}/{MIN_RESOLVED_CALLS}")
    if days < MIN_RESOLVED_DAYS:
        blockers.append(f"days {days}/{MIN_RESOLVED_DAYS}")
    if pitchers < MIN_PITCHERS:
        blockers.append(f"pitchers {pitchers}/{MIN_PITCHERS}")
    if coverage < MIN_PROBABILITY_COVERAGE:
        blockers.append(f"probability coverage {coverage:.1%}/{MIN_PROBABILITY_COVERAGE:.0%}")
    reason = (
        "Maturity reached for manual review of ladder reliability/calibration. This is a model-supported milestone study, not sportsbook execution evidence."
        if mature else
        "Need " + ", ".join(blockers) + " before manual research review."
    )
    return pd.DataFrame([{
        "Status": status,
        "Resolved_Calls": calls,
        "Required_Calls": MIN_RESOLVED_CALLS,
        "Resolved_Days": days,
        "Required_Days": MIN_RESOLVED_DAYS,
        "Distinct_Pitchers": pitchers,
        "Required_Pitchers": MIN_PITCHERS,
        "Probability_Coverage": coverage,
        "Required_Probability_Coverage": MIN_PROBABILITY_COVERAGE,
        "Ladder_Win_Rate": hit_rate,
        "Avg_Target_Probability": avg_prob,
        "Calibration_Gap": calibration_gap,
        "Brier_Score": brier,
        "Cohorts_Tracked": int(len(cohorts)) if cohorts is not None else 0,
        "Ready_For_Manual_Review": mature,
        "Recommended_Action": "MANUAL_RESEARCH_REVIEW" if mature else "COLLECT_LADDER_RELIABILITY_EVIDENCE",
        "Reason": reason,
        "Report_Only": REPORT_ONLY,
        "Production_Authority": PRODUCTION_AUTHORITY,
        "No_Projection_Adjustment": NO_PROJECTION_ADJUSTMENT,
        "Research_Version": VERSION,
    }])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build report-only K ladder reliability shadow research.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/k_ladder_reliability_shadow_detail.csv"))
    parser.add_argument("--cohorts", type=Path, default=Path("data/k_ladder_reliability_shadow_cohorts.csv"))
    parser.add_argument("--gate", type=Path, default=Path("data/k_ladder_reliability_shadow_gate.csv"))
    args = parser.parse_args()
    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    detail = build_detail(history)
    cohorts = build_cohort_summary(detail)
    gate = build_gate(detail, cohorts)
    for frame, path in ((detail, args.detail), (cohorts, args.cohorts), (gate, args.gate)):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    print(gate.to_string(index=False))


if __name__ == "__main__":
    main()
