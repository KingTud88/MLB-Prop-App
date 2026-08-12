from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from training.workload_backtest import build_backtest
from training.workload_leash_backtest import attach_walk_forward_leash_candidate

# Fixed before the 2024 holdout is inspected: keep the global workload-v2 bias
# correction everywhere except TIGHT leash starts, where the hierarchical
# leakage-safe leash correction is used. NORMAL and LONG are deliberately left
# on global v2. Sportsbook/market/bet data is never used.
TIGHT_CANDIDATE_VERSION = "workload-v2.2-tight-only-candidate"
TIGHT_LABEL = "TIGHT"
MIN_STATUS_STARTS = 30
MIN_RELATIVE_MAE = 0.0025
METRICS = ("pitches", "bf", "outs")


def _numeric(series: object, index: pd.Index | None = None) -> pd.Series:
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce")
    if index is None:
        return pd.Series(dtype=float)
    return pd.Series(np.nan, index=index, dtype=float)


def attach_tight_only_candidate(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame.copy()
    work = frame.copy()
    if "leash_candidate_pitches" not in work.columns:
        work = attach_walk_forward_leash_candidate(work)
    labels = work.get("leash_label", pd.Series("UNKNOWN", index=work.index)).fillna("UNKNOWN").astype(str)
    tight = labels.eq(TIGHT_LABEL)
    work["tight_candidate_version"] = TIGHT_CANDIDATE_VERSION
    work["tight_candidate_applied"] = tight
    for metric in METRICS:
        global_candidate = _numeric(work.get(f"candidate_{metric}"), work.index)
        leash_candidate = _numeric(work.get(f"leash_candidate_{metric}"), work.index)
        final = global_candidate.copy()
        final.loc[tight] = leash_candidate.loc[tight]
        work[f"tight_candidate_{metric}"] = final
    return work


def _metric_summary(frame: pd.DataFrame, metric: str) -> dict[str, object] | None:
    actual = _numeric(frame.get(f"actual_{metric}"), frame.index)
    workload = _numeric(frame.get(f"workload_{metric}"), frame.index)
    global_candidate = _numeric(frame.get(f"candidate_{metric}"), frame.index)
    tight_candidate = _numeric(frame.get(f"tight_candidate_{metric}"), frame.index)
    ready = actual.notna() & workload.notna() & global_candidate.notna() & tight_candidate.notna()
    if not ready.any():
        return None

    a = actual[ready].astype(float)
    w = workload[ready].astype(float)
    g = global_candidate[ready].astype(float)
    t = tight_candidate[ready].astype(float)
    w_err = w - a
    g_err = g - a
    t_err = t - a
    w_mae = float(w_err.abs().mean())
    g_mae = float(g_err.abs().mean())
    t_mae = float(t_err.abs().mean())
    rel_vs_workload = float((w_mae - t_mae) / w_mae) if w_mae > 0 else float("nan")
    rel_vs_global = float((g_mae - t_mae) / g_mae) if g_mae > 0 else float("nan")

    applied = frame.get("tight_candidate_applied", pd.Series(False, index=frame.index)).fillna(False).astype(bool)
    changed = ready & applied & (tight_candidate - global_candidate).abs().gt(1e-12)
    changed_n = int(changed.sum())
    if changed_n:
        t_changed = (tight_candidate[changed].astype(float) - actual[changed].astype(float)).abs()
        g_changed = (global_candidate[changed].astype(float) - actual[changed].astype(float)).abs()
        w_changed = (workload[changed].astype(float) - actual[changed].astype(float)).abs()
        win_vs_global = float((t_changed < g_changed).mean())
        win_vs_workload = float((t_changed < w_changed).mean())
    else:
        win_vs_global = win_vs_workload = float("nan")

    t_bias = float(t_err.mean())
    g_bias = float(g_err.mean())
    if changed_n < MIN_STATUS_STARTS:
        status = "LEARNING"
    elif rel_vs_global >= MIN_RELATIVE_MAE and abs(t_bias) <= abs(g_bias) and win_vs_global >= 0.50:
        status = "HELPING"
    elif rel_vs_global <= -MIN_RELATIVE_MAE and abs(t_bias) >= abs(g_bias) and win_vs_global <= 0.50:
        status = "HURTING"
    else:
        status = "MIXED"

    return {
        "Metric": metric.upper(),
        "Evaluated_Starts": int(ready.sum()),
        "Workload_v1_MAE": w_mae,
        "Global_v2_MAE": g_mae,
        "Tight_v22_MAE": t_mae,
        "Tight_v22_RMSE": float(np.sqrt(np.mean(np.square(t_err)))),
        "Global_v2_Bias": g_bias,
        "Tight_v22_Bias": t_bias,
        "Relative_MAE_vs_Workload_v1": rel_vs_workload,
        "Relative_MAE_vs_Global_v2": rel_vs_global,
        "Tight_Adjusted_Starts": changed_n,
        "Tight_Win_Share_vs_Workload_v1": win_vs_workload,
        "Tight_Win_Share_vs_Global_v2": win_vs_global,
        "Tight_Status": status,
        "Candidate_Version": TIGHT_CANDIDATE_VERSION,
    }


def summarize_tight_candidate(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    work = frame if "tight_candidate_pitches" in frame.columns else attach_tight_only_candidate(frame)
    rows = [_metric_summary(work, metric) for metric in METRICS]
    return pd.DataFrame([row for row in rows if row is not None])


def tight_segment_report(frame: pd.DataFrame, min_starts: int = 15) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    work = frame if "tight_candidate_pitches" in frame.columns else attach_tight_only_candidate(frame)
    labels = work.get("leash_label", pd.Series("UNKNOWN", index=work.index)).fillna("UNKNOWN").astype(str)
    rows: list[dict[str, object]] = []
    for label, group in work.groupby(labels, dropna=False):
        for metric in METRICS:
            summary = _metric_summary(group, metric)
            if summary is None or int(summary["Evaluated_Starts"]) < int(min_starts):
                continue
            rows.append({"Leash": str(label), **summary})
    return pd.DataFrame(rows)


def build_multi_season_report(projection_log: pd.DataFrame, seasons: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    summaries: list[pd.DataFrame] = []
    segments: list[pd.DataFrame] = []
    for season in seasons:
        detail = build_backtest(projection_log, target_season=int(season))
        if detail.empty:
            continue
        candidate = attach_tight_only_candidate(detail)
        summary = summarize_tight_candidate(candidate)
        segment = tight_segment_report(candidate)
        summary.insert(0, "Season", int(season))
        if not segment.empty:
            segment.insert(0, "Season", int(season))
        summaries.append(summary)
        if not segment.empty:
            segments.append(segment)
    return (
        pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame(),
        pd.concat(segments, ignore_index=True) if segments else pd.DataFrame(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-only workload-v2.2 TIGHT-leash candidate with 2024 holdout validation.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--seasons", type=int, nargs="+", default=[2024, 2025, 2026])
    parser.add_argument("--summary", type=Path, default=Path("data/workload_v22_summary.csv"))
    parser.add_argument("--segments", type=Path, default=Path("data/workload_v22_segments.csv"))
    args = parser.parse_args()

    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    summary, segments = build_multi_season_report(history, [int(x) for x in args.seasons])
    if summary.empty:
        raise SystemExit("No workload-v2.2 validation rows were produced")
    for path in (args.summary, args.segments):
        path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary, index=False)
    segments.to_csv(args.segments, index=False)
    print(summary.to_string(index=False))
    print(f"seasons={sorted(summary['Season'].unique().tolist())} candidate={TIGHT_CANDIDATE_VERSION}")


if __name__ == "__main__":
    main()
