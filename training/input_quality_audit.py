from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

QUALITY_VERSION = "input-quality-v1-report-only"
COHORT_VERSION = "input-quality-cohort-v1-report-only"
MIN_COHORT_SIDE = 20
METRICS = {
    "strikeouts": ("projection", "actual_strikeouts"),
    "hits": ("hits_projection", "actual_hits_allowed"),
    "outs": ("outs_projection", "actual_outs"),
}


def _num(frame: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(frame[col], errors="coerce") if col in frame.columns else pd.Series(np.nan, index=frame.index)


def attach_input_quality(frame: pd.DataFrame) -> pd.DataFrame:
    """Score only information already available at projection capture time."""
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame.copy()
    work = frame.copy()
    lineup_confirmed = work.get("lineup_confirmed", pd.Series(False, index=work.index)).fillna(False).astype(str).str.lower().isin({"true", "1", "yes"})
    history = _num(work, "starter_history_games").fillna(0)
    workload = _num(work, "workload_starts_used").fillna(0)
    weather = work.get("weather_summary", pd.Series("", index=work.index)).fillna("").astype(str).str.strip().ne("")
    role = work.get("starter_role_label", pd.Series("", index=work.index)).fillna("").astype(str).str.strip().ne("")

    # Fixed before outcome analysis. The score is descriptive only and has no
    # authority to alter projections, rankings, probabilities, or bet advice.
    score = (
        lineup_confirmed.astype(int) * 2
        + history.ge(5).astype(int) * 2
        + workload.ge(5).astype(int) * 2
        + weather.astype(int)
        + role.astype(int)
    )
    work["input_quality_version"] = QUALITY_VERSION
    work["input_quality_score"] = score.astype(int)
    work["input_quality_tier"] = pd.cut(score, bins=[-1, 3, 5, 8], labels=["LOW", "MEDIUM", "HIGH"]).astype(str)
    work["iq_lineup_confirmed"] = lineup_confirmed
    work["iq_history_5p"] = history.ge(5)
    work["iq_workload_5p"] = workload.ge(5)
    work["iq_weather_present"] = weather
    work["iq_role_present"] = role
    return work


def quality_summary(frame: pd.DataFrame) -> pd.DataFrame:
    work = attach_input_quality(frame) if "input_quality_score" not in frame.columns else frame.copy()
    rows = []
    for tier, group in work.groupby("input_quality_tier", dropna=False):
        for metric, (pred_col, actual_col) in METRICS.items():
            pred, actual = _num(group, pred_col), _num(group, actual_col)
            ready = pred.notna() & actual.notna()
            if not ready.any():
                continue
            err = pred[ready].astype(float) - actual[ready].astype(float)
            rows.append({
                "Quality_Tier": str(tier),
                "Metric": metric.upper(),
                "Resolved_Starts": int(ready.sum()),
                "MAE": float(err.abs().mean()),
                "RMSE": float(np.sqrt(np.mean(np.square(err)))),
                "Bias": float(err.mean()),
                "Mean_Quality_Score": float(_num(group.loc[ready], "input_quality_score").mean()),
                "Audit_Version": QUALITY_VERSION,
            })
    return pd.DataFrame(rows)


def component_report(frame: pd.DataFrame) -> pd.DataFrame:
    work = attach_input_quality(frame) if "input_quality_score" not in frame.columns else frame.copy()
    components = ["iq_lineup_confirmed", "iq_history_5p", "iq_workload_5p", "iq_weather_present", "iq_role_present"]
    rows = []
    for component in components:
        flag = work.get(component, pd.Series(False, index=work.index)).fillna(False).astype(bool)
        for present, group in work.groupby(flag):
            for metric, (pred_col, actual_col) in METRICS.items():
                pred, actual = _num(group, pred_col), _num(group, actual_col)
                ready = pred.notna() & actual.notna()
                if not ready.any():
                    continue
                err = pred[ready].astype(float) - actual[ready].astype(float)
                rows.append({
                    "Component": component,
                    "Present": bool(present),
                    "Metric": metric.upper(),
                    "Resolved_Starts": int(ready.sum()),
                    "MAE": float(err.abs().mean()),
                    "Bias": float(err.mean()),
                    "Audit_Version": QUALITY_VERSION,
                })
    return pd.DataFrame(rows)


def cohort_report(frame: pd.DataFrame, min_side: int = MIN_COHORT_SIDE) -> pd.DataFrame:
    """Compare input-depth groups only within same season-month cohorts.

    This is descriptive research only. Cohorts are scored only when both the
    shallow and deep side have at least ``min_side`` resolved starts for the
    metric. No pooled result is allowed to hide an underpowered cohort.
    """
    work = attach_input_quality(frame) if "input_quality_score" not in frame.columns else frame.copy()
    dates = pd.to_datetime(work.get("game_date"), errors="coerce")
    work["_season"] = dates.dt.year
    work["_month"] = dates.dt.month
    rows: list[dict[str, object]] = []
    comparisons = {
        "starter_history_5p": "iq_history_5p",
        "workload_history_5p": "iq_workload_5p",
    }
    for (season, month), cohort in work.groupby(["_season", "_month"], dropna=True):
        for comparison, flag_col in comparisons.items():
            flag = cohort.get(flag_col, pd.Series(False, index=cohort.index)).fillna(False).astype(bool)
            for metric, (pred_col, actual_col) in METRICS.items():
                pred, actual = _num(cohort, pred_col), _num(cohort, actual_col)
                ready = pred.notna() & actual.notna()
                shallow = ready & ~flag
                deep = ready & flag
                n_shallow, n_deep = int(shallow.sum()), int(deep.sum())
                powered = n_shallow >= int(min_side) and n_deep >= int(min_side)
                shallow_mae = float((pred[shallow] - actual[shallow]).abs().mean()) if n_shallow else float("nan")
                deep_mae = float((pred[deep] - actual[deep]).abs().mean()) if n_deep else float("nan")
                shallow_bias = float((pred[shallow] - actual[shallow]).mean()) if n_shallow else float("nan")
                deep_bias = float((pred[deep] - actual[deep]).mean()) if n_deep else float("nan")
                rel = float((shallow_mae - deep_mae) / shallow_mae) if powered and shallow_mae > 0 else float("nan")
                if not powered:
                    status = "LEARNING"
                elif rel >= 0.01 and abs(deep_bias) <= abs(shallow_bias):
                    status = "SUPPORTIVE"
                elif rel <= -0.01 and abs(deep_bias) >= abs(shallow_bias):
                    status = "CONTRADICTORY"
                else:
                    status = "MIXED"
                rows.append({
                    "Season": int(season),
                    "Month": int(month),
                    "Comparison": comparison,
                    "Metric": metric.upper(),
                    "Shallow_Starts": n_shallow,
                    "Deep_Starts": n_deep,
                    "Shallow_MAE": shallow_mae,
                    "Deep_MAE": deep_mae,
                    "Relative_MAE_Improvement": rel,
                    "Shallow_Bias": shallow_bias,
                    "Deep_Bias": deep_bias,
                    "Powered": bool(powered),
                    "Status": status,
                    "Min_Side": int(min_side),
                    "Audit_Version": COHORT_VERSION,
                })
    return pd.DataFrame(rows)


def cohort_summary(cohorts: pd.DataFrame) -> pd.DataFrame:
    if cohorts is None or cohorts.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for (comparison, metric), group in cohorts.groupby(["Comparison", "Metric"]):
        powered = group[group["Powered"].astype(bool)].copy()
        if powered.empty:
            rows.append({
                "Comparison": comparison,
                "Metric": metric,
                "Powered_Cohorts": 0,
                "Supportive_Cohorts": 0,
                "Contradictory_Cohorts": 0,
                "Median_Relative_MAE_Improvement": float("nan"),
                "Status": "LEARNING",
                "Audit_Version": COHORT_VERSION,
            })
            continue
        supportive = int(powered["Status"].eq("SUPPORTIVE").sum())
        contradictory = int(powered["Status"].eq("CONTRADICTORY").sum())
        median_rel = float(pd.to_numeric(powered["Relative_MAE_Improvement"], errors="coerce").median())
        if len(powered) >= 2 and supportive > contradictory and median_rel >= 0.01:
            status = "SUPPORTIVE"
        elif len(powered) >= 2 and contradictory > supportive and median_rel <= -0.01:
            status = "CONTRADICTORY"
        else:
            status = "MIXED"
        rows.append({
            "Comparison": comparison,
            "Metric": metric,
            "Powered_Cohorts": int(len(powered)),
            "Supportive_Cohorts": supportive,
            "Contradictory_Cohorts": contradictory,
            "Median_Relative_MAE_Improvement": median_rel,
            "Status": status,
            "Audit_Version": COHORT_VERSION,
        })
    return pd.DataFrame(rows)


def main() -> None:
    p = argparse.ArgumentParser(description="Report-only projection input quality audit")
    p.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    p.add_argument("--summary", type=Path, default=Path("data/input_quality_summary.csv"))
    p.add_argument("--components", type=Path, default=Path("data/input_quality_components.csv"))
    p.add_argument("--cohorts", type=Path, default=Path("data/input_quality_cohorts.csv"))
    p.add_argument("--cohort-summary", type=Path, default=Path("data/input_quality_cohort_summary.csv"))
    args = p.parse_args()
    log = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if log.empty:
        raise SystemExit("No projection history available")
    scored = attach_input_quality(log)
    summary = quality_summary(scored)
    components = component_report(scored)
    cohorts = cohort_report(scored)
    cohort_rollup = cohort_summary(cohorts)
    if summary.empty:
        raise SystemExit("No resolved starts available for input-quality audit")
    for path in (args.summary, args.components, args.cohorts, args.cohort_summary):
        path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary, index=False)
    components.to_csv(args.components, index=False)
    cohorts.to_csv(args.cohorts, index=False)
    cohort_rollup.to_csv(args.cohort_summary, index=False)
    print(summary.to_string(index=False))
    print("\nCohort-controlled summary")
    print(cohort_rollup.to_string(index=False))


if __name__ == "__main__":
    main()
