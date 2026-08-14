from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

QUALITY_VERSION = "input-quality-v1-report-only"
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


def main() -> None:
    p = argparse.ArgumentParser(description="Report-only projection input quality audit")
    p.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    p.add_argument("--summary", type=Path, default=Path("data/input_quality_summary.csv"))
    p.add_argument("--components", type=Path, default=Path("data/input_quality_components.csv"))
    args = p.parse_args()
    log = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if log.empty:
        raise SystemExit("No projection history available")
    scored = attach_input_quality(log)
    summary = quality_summary(scored)
    components = component_report(scored)
    if summary.empty:
        raise SystemExit("No resolved starts available for input-quality audit")
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.components.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary, index=False)
    components.to_csv(args.components, index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
