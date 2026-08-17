from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from engine.projection_crushers import bettable_k_target
from engine.starter_history import HISTORY_SEMANTICS

CRUSHER_V2_VERSION = "projection-crusher-v2-report-only"
PRODUCTION_AUTHORITY = "NONE"
MIN_COHORT_STARTS = 5


def _num(series: object, index: pd.Index) -> pd.Series:
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce")
    return pd.Series(np.nan, index=index, dtype=float)


def _prob(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return None
    number = float(parsed)
    if number > 1.0 and number <= 100.0:
        number /= 100.0
    if number < 0.0 or number > 1.0:
        return None
    return number


def _target_probability(row: pd.Series, target: int) -> float | None:
    values = [_prob(row.get(f"sim_{target}p")), _prob(row.get(f"math_{target}p"))]
    ready = [value for value in values if value is not None]
    return float(np.mean(ready)) if ready else None


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "confirmed"}


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


def _headroom_bucket(value: float) -> str:
    if value < 0.25:
        return "0.00-0.24"
    if value < 0.50:
        return "0.25-0.49"
    if value < 0.75:
        return "0.50-0.74"
    return "0.75-0.99"


def _opponent_k_bucket(value: object) -> str:
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
    frame["Actual_Margin"] = frame["Actual_K"] - frame["K_Target"].astype(float)
    frame["Ladder_Win"] = frame["Actual_Margin"].ge(0.0)
    frame["Crusher_Event"] = frame["Actual_Margin"].ge(2.0)
    frame["Mega_Crusher_Event"] = frame["Actual_Margin"].ge(3.0)
    frame["Raw_Path_Target_Probability"] = frame.apply(
        lambda row: _target_probability(row, int(row["K_Target"])), axis=1
    )
    frame["Data_Quality"] = _num(frame.get("data_quality"), frame.index)
    frame["Data_Quality_Bucket"] = frame.get("data_quality", pd.Series(index=frame.index, dtype=object)).map(_quality_bucket)
    frame["Confidence"] = frame.get("confidence", pd.Series("UNKNOWN", index=frame.index)).fillna("UNKNOWN").astype(str).str.upper()
    frame["Headroom_Bucket"] = frame["Projection_Headroom"].map(_headroom_bucket)
    frame["Opponent_K_Bucket"] = frame.get("opponent_k_pct", pd.Series(index=frame.index, dtype=float)).map(_opponent_k_bucket)
    frame["Lineup_State"] = frame.get("lineup_confirmed", pd.Series(False, index=frame.index)).map(
        lambda value: "CONFIRMED" if _truthy(value) else "PROJECTED_OR_UNKNOWN"
    )
    frame["Weather_Risk"] = frame.get("weather_delay_risk", pd.Series("UNKNOWN", index=frame.index)).fillna("UNKNOWN").astype(str).str.upper()
    frame["Leash_Label"] = frame.get("leash_label", pd.Series("UNKNOWN", index=frame.index)).fillna("UNKNOWN").astype(str).str.upper()
    frame["Starter_Role"] = frame.get("starter_role_label", pd.Series("UNKNOWN", index=frame.index)).fillna("UNKNOWN").astype(str).str.upper()
    frame["Game_Date"] = pd.to_datetime(frame.get("game_date"), errors="coerce").dt.date.astype(str)
    frame["Pitcher"] = frame.get("player", pd.Series("Unknown", index=frame.index)).fillna("Unknown").astype(str)

    columns = [
        "Game_Date", "Pitcher", "team", "opponent", "Target_Label", "Projection", "Actual_K",
        "Projection_Headroom", "Actual_Margin", "Ladder_Win", "Crusher_Event", "Mega_Crusher_Event",
        "Raw_Path_Target_Probability", "Confidence", "Data_Quality", "Data_Quality_Bucket",
        "Headroom_Bucket", "Opponent_K_Bucket", "Lineup_State", "Weather_Risk", "Leash_Label", "Starter_Role",
    ]
    for column in columns:
        if column not in frame.columns:
            frame[column] = pd.NA
    out = frame[columns].copy()
    out["Production_Authority"] = PRODUCTION_AUTHORITY
    out["Report_Only"] = True
    out["Crusher_Version"] = CRUSHER_V2_VERSION
    return out.reset_index(drop=True)


def build_pitcher_summary(detail: pd.DataFrame) -> pd.DataFrame:
    if detail is None or detail.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for pitcher, group in detail.groupby("Pitcher", dropna=False):
        wins = int(group["Ladder_Win"].astype(bool).sum())
        crushers = int(group["Crusher_Event"].astype(bool).sum())
        rows.append({
            "Pitcher": str(pitcher),
            "Resolved_Calls": int(len(group)),
            "Ladder_Wins": wins,
            "Win_Rate": float(wins / len(group)),
            "Crusher_Events": crushers,
            "Crusher_Rate": float(crushers / len(group)),
            "Mega_Crusher_Events": int(group["Mega_Crusher_Event"].astype(bool).sum()),
            "Avg_Actual_Margin": float(pd.to_numeric(group["Actual_Margin"], errors="coerce").mean()),
            "Avg_Raw_Path_Target_Probability": float(pd.to_numeric(group["Raw_Path_Target_Probability"], errors="coerce").mean()),
            "Avg_Data_Quality": float(pd.to_numeric(group["Data_Quality"], errors="coerce").mean()),
            "Production_Authority": PRODUCTION_AUTHORITY,
            "Report_Only": True,
            "Crusher_Version": CRUSHER_V2_VERSION,
        })
    return pd.DataFrame(rows).sort_values(
        ["Crusher_Events", "Crusher_Rate", "Ladder_Wins", "Avg_Actual_Margin", "Resolved_Calls"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)


def build_cohort_summary(detail: pd.DataFrame) -> pd.DataFrame:
    columns = [
        ("Target", "Target_Label"),
        ("Confidence", "Confidence"),
        ("Data Quality", "Data_Quality_Bucket"),
        ("Projection Headroom", "Headroom_Bucket"),
        ("Opponent K Environment", "Opponent_K_Bucket"),
        ("Lineup State", "Lineup_State"),
        ("Weather Risk", "Weather_Risk"),
        ("Leash", "Leash_Label"),
        ("Starter Role", "Starter_Role"),
    ]
    if detail is None or detail.empty:
        return pd.DataFrame()
    overall_crusher_rate = float(detail["Crusher_Event"].astype(bool).mean())
    rows: list[dict[str, object]] = []
    for dimension, column in columns:
        for cohort, group in detail.groupby(column, dropna=False):
            n = int(len(group))
            if n < MIN_COHORT_STARTS:
                continue
            crusher_rate = float(group["Crusher_Event"].astype(bool).mean())
            lift = crusher_rate - overall_crusher_rate
            if n < 10:
                signal = "LEARNING"
            elif lift >= 0.10:
                signal = "OVERINDEX"
            elif lift <= -0.10:
                signal = "UNDERINDEX"
            else:
                signal = "NEUTRAL"
            rows.append({
                "Dimension": dimension,
                "Cohort": str(cohort),
                "Resolved_Calls": n,
                "Ladder_Win_Rate": float(group["Ladder_Win"].astype(bool).mean()),
                "Crusher_Events": int(group["Crusher_Event"].astype(bool).sum()),
                "Crusher_Rate": crusher_rate,
                "Crusher_Rate_Lift_vs_Overall": lift,
                "Avg_Actual_Margin": float(pd.to_numeric(group["Actual_Margin"], errors="coerce").mean()),
                "Avg_Raw_Path_Target_Probability": float(pd.to_numeric(group["Raw_Path_Target_Probability"], errors="coerce").mean()),
                "Avg_Data_Quality": float(pd.to_numeric(group["Data_Quality"], errors="coerce").mean()),
                "Signal": signal,
                "Production_Authority": PRODUCTION_AUTHORITY,
                "Report_Only": True,
                "Crusher_Version": CRUSHER_V2_VERSION,
            })
    return pd.DataFrame(rows).sort_values(
        ["Dimension", "Crusher_Rate", "Resolved_Calls"], ascending=[True, False, False]
    ).reset_index(drop=True)


def build_coverage(detail: pd.DataFrame) -> pd.DataFrame:
    n = int(len(detail)) if detail is not None else 0
    if not n:
        return pd.DataFrame([{
            "Resolved_Calls": 0,
            "Crusher_Events": 0,
            "Crusher_Rate": np.nan,
            "Probability_Coverage": 0.0,
            "Data_Quality_Coverage": 0.0,
            "Confirmed_Lineup_Coverage": 0.0,
            "Weather_Context_Coverage": 0.0,
            "Starter_Role_Coverage": 0.0,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "Report_Only": True,
            "Crusher_Version": CRUSHER_V2_VERSION,
        }])
    return pd.DataFrame([{
        "Resolved_Calls": n,
        "Crusher_Events": int(detail["Crusher_Event"].astype(bool).sum()),
        "Crusher_Rate": float(detail["Crusher_Event"].astype(bool).mean()),
        "Probability_Coverage": float(detail["Raw_Path_Target_Probability"].notna().mean()),
        "Data_Quality_Coverage": float(detail["Data_Quality"].notna().mean()),
        "Confirmed_Lineup_Coverage": float(detail["Lineup_State"].eq("CONFIRMED").mean()),
        "Weather_Context_Coverage": float((~detail["Weather_Risk"].isin(["", "UNKNOWN", "NAN"])).mean()),
        "Starter_Role_Coverage": float((~detail["Starter_Role"].isin(["", "UNKNOWN", "NAN"])).mean()),
        "Production_Authority": PRODUCTION_AUTHORITY,
        "Report_Only": True,
        "Crusher_Version": CRUSHER_V2_VERSION,
    }])


def main() -> None:
    parser = argparse.ArgumentParser(description="Projection Crusher v2 descriptive intelligence report")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--detail", type=Path, default=Path("data/projection_crusher_v2_detail.csv"))
    parser.add_argument("--pitchers", type=Path, default=Path("data/projection_crusher_v2_pitchers.csv"))
    parser.add_argument("--cohorts", type=Path, default=Path("data/projection_crusher_v2_cohorts.csv"))
    parser.add_argument("--coverage", type=Path, default=Path("data/projection_crusher_v2_coverage.csv"))
    args = parser.parse_args()

    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if history.empty:
        raise SystemExit("Projection log is missing or empty")
    detail = build_detail(history)
    pitchers = build_pitcher_summary(detail)
    cohorts = build_cohort_summary(detail)
    coverage = build_coverage(detail)
    for path in (args.detail, args.pitchers, args.cohorts, args.coverage):
        path.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.detail, index=False)
    pitchers.to_csv(args.pitchers, index=False)
    cohorts.to_csv(args.cohorts, index=False)
    coverage.to_csv(args.coverage, index=False)
    print(coverage.to_string(index=False))
    print(f"version={CRUSHER_V2_VERSION} production_authority={PRODUCTION_AUTHORITY}")


if __name__ == "__main__":
    main()
