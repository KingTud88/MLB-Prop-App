from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

AUDIT_VERSION = "lineup-sensitivity-v1-report-only"
MIN_PAIRED_STARTS = 20
MIN_RELATIVE_MAE = 0.01
METRICS = {
    "STRIKEOUTS": ("lineup_preconfirm_projection", "projection", "actual_strikeouts", "lineup_projection_delta"),
    "HITS": ("lineup_preconfirm_hits_projection", "hits_projection", "actual_hits_allowed", "lineup_hits_projection_delta"),
}


def _num(frame: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(frame[col], errors="coerce") if col in frame.columns else pd.Series(np.nan, index=frame.index)


def _confirmed(frame: pd.DataFrame) -> pd.Series:
    raw = frame.get("lineup_confirmed", pd.Series(False, index=frame.index))
    return raw.fillna(False).astype(str).str.lower().isin({"true", "1", "yes"})


def _metric_summary(frame: pd.DataFrame, metric: str) -> dict[str, object] | None:
    pre_col, post_col, actual_col, delta_col = METRICS[metric]
    pre = _num(frame, pre_col)
    post = _num(frame, post_col)
    actual = _num(frame, actual_col)
    changed = _num(frame, delta_col)
    ready = _confirmed(frame) & pre.notna() & post.notna() & actual.notna()
    if not ready.any():
        return None

    pre_err = pre[ready].astype(float) - actual[ready].astype(float)
    post_err = post[ready].astype(float) - actual[ready].astype(float)
    pre_abs = pre_err.abs()
    post_abs = post_err.abs()
    n = int(ready.sum())
    pre_mae = float(pre_abs.mean())
    post_mae = float(post_abs.mean())
    rel = float((pre_mae - post_mae) / pre_mae) if pre_mae > 0 else float("nan")
    win = float((post_abs < pre_abs).mean())
    loss = float((post_abs > pre_abs).mean())
    tie = float((post_abs == pre_abs).mean())
    pre_bias = float(pre_err.mean())
    post_bias = float(post_err.mean())
    mean_abs_change = float(changed[ready].abs().mean()) if changed[ready].notna().any() else float((post[ready] - pre[ready]).abs().mean())

    if n < MIN_PAIRED_STARTS:
        status = "LEARNING"
    elif rel >= MIN_RELATIVE_MAE and win >= 0.50 and abs(post_bias) <= abs(pre_bias):
        status = "HELPING"
    elif rel <= -MIN_RELATIVE_MAE and loss >= 0.50 and abs(post_bias) >= abs(pre_bias):
        status = "HURTING"
    else:
        status = "MIXED"

    return {
        "Metric": metric,
        "Paired_Starts": n,
        "Preconfirm_MAE": pre_mae,
        "Confirmed_MAE": post_mae,
        "Relative_MAE_Improvement": rel,
        "Confirmed_Win_Share": win,
        "Confirmed_Loss_Share": loss,
        "Tie_Share": tie,
        "Preconfirm_Bias": pre_bias,
        "Confirmed_Bias": post_bias,
        "Mean_Absolute_Projection_Change": mean_abs_change,
        "Status": status,
        "Audit_Version": AUDIT_VERSION,
    }


def paired_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows = [_metric_summary(frame, metric) for metric in METRICS]
    return pd.DataFrame([row for row in rows if row is not None])


def magnitude_report(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for metric, (pre_col, post_col, actual_col, delta_col) in METRICS.items():
        pre = _num(frame, pre_col)
        post = _num(frame, post_col)
        actual = _num(frame, actual_col)
        delta = _num(frame, delta_col)
        ready = _confirmed(frame) & pre.notna() & post.notna() & actual.notna()
        if not ready.any():
            continue
        work = pd.DataFrame({"pre": pre[ready], "post": post[ready], "actual": actual[ready], "delta": delta[ready]})
        work["abs_delta"] = work["delta"].abs().fillna((work["post"] - work["pre"]).abs())
        work["bucket"] = pd.cut(work["abs_delta"], bins=[-1e-12, 0.10, 0.25, 0.50, np.inf], labels=["<=0.10", "0.10-0.25", "0.25-0.50", ">0.50"])
        for bucket, group in work.groupby("bucket", observed=False):
            if group.empty:
                continue
            pre_abs = (group["pre"] - group["actual"]).abs()
            post_abs = (group["post"] - group["actual"]).abs()
            rows.append({
                "Metric": metric,
                "Absolute_Change_Bucket": str(bucket),
                "Paired_Starts": int(len(group)),
                "Preconfirm_MAE": float(pre_abs.mean()),
                "Confirmed_MAE": float(post_abs.mean()),
                "Confirmed_Win_Share": float((post_abs < pre_abs).mean()),
                "Audit_Version": AUDIT_VERSION,
            })
    return pd.DataFrame(rows)


def main() -> None:
    p = argparse.ArgumentParser(description="Report-only paired pre-confirm vs confirmed lineup projection audit")
    p.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    p.add_argument("--summary", type=Path, default=Path("data/lineup_sensitivity_summary.csv"))
    p.add_argument("--magnitude", type=Path, default=Path("data/lineup_sensitivity_magnitude.csv"))
    args = p.parse_args()
    log = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if log.empty:
        raise SystemExit("No projection history available")
    summary = paired_summary(log)
    magnitude = magnitude_report(log)
    if summary.empty:
        raise SystemExit("No paired confirmed-lineup projections available")
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.magnitude.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary, index=False)
    magnitude.to_csv(args.magnitude, index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
