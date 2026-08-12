from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from training.workload_backtest import (
    BIAS_CANDIDATE_VERSION,
    BIAS_CAPS,
    build_backtest,
)

# Report-only follow-up to the global workload-v2 bias candidate. The leash
# candidate is hierarchical: a leash-label residual estimate is shrunk hard
# toward the already leakage-safe global correction. Only strictly earlier game
# dates are eligible. Sportsbook data, market prices, bets, same-day outcomes,
# and future outcomes are never inputs.
LEASH_CANDIDATE_VERSION = "workload-v2.1-leash-candidate"
LEASH_MIN_OBSERVATIONS = 30
LEASH_WINDOW = 180
LEASH_PRIOR_STRENGTH = 90.0
LEASH_MIN_RELATIVE_MAE = 0.0025
MIN_STATUS_STARTS = 30
METRICS = ("pitches", "bf", "outs")


def _numeric(series: object, index: pd.Index | None = None) -> pd.Series:
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce")
    if index is None:
        return pd.Series(dtype=float)
    return pd.Series(np.nan, index=index, dtype=float)


def attach_walk_forward_leash_candidate(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach a hierarchical leash correction using strictly earlier dates.

    The global workload-v2 correction remains the prior. Once a leash label has
    at least LEASH_MIN_OBSERVATIONS earlier resolved starts, its own mean
    residual is blended toward that global correction using
    LEASH_PRIOR_STRENGTH. This prevents small segment samples from dominating.
    """
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame.copy()

    work = frame.copy()
    work["_game_date_dt"] = pd.to_datetime(work.get("game_date"), errors="coerce")
    work["_leash_label"] = work.get("leash_label", pd.Series("UNKNOWN", index=work.index)).fillna("UNKNOWN").astype(str)
    work["leash_candidate_version"] = LEASH_CANDIDATE_VERSION
    work["leash_global_candidate_version"] = BIAS_CANDIDATE_VERSION

    for metric in METRICS:
        workload = _numeric(work.get(f"workload_{metric}"), work.index)
        global_candidate = _numeric(work.get(f"candidate_{metric}"), work.index)
        if global_candidate.isna().all():
            global_candidate = workload.copy()
        global_correction = _numeric(work.get(f"bias_correction_{metric}"), work.index).fillna(0.0)
        work[f"leash_prior_n_{metric}"] = 0
        work[f"leash_correction_{metric}"] = global_correction.astype(float)
        work[f"leash_candidate_{metric}"] = global_candidate.astype(float)

    normalized = work["_game_date_dt"].dt.normalize()
    game_dates = sorted(normalized.dropna().drop_duplicates().tolist())
    for game_date in game_dates:
        current_mask = normalized.eq(game_date)
        prior_mask = normalized.lt(game_date)
        prior = work.loc[prior_mask]
        if prior.empty:
            continue

        labels = work.loc[current_mask, "_leash_label"].drop_duplicates().tolist()
        for label in labels:
            label_current = current_mask & work["_leash_label"].eq(label)
            label_prior = prior.loc[prior["_leash_label"].eq(label)]
            for metric in METRICS:
                actual = _numeric(label_prior.get(f"actual_{metric}"), label_prior.index)
                baseline = _numeric(label_prior.get(f"workload_{metric}"), label_prior.index)
                residual = (actual - baseline).dropna().tail(LEASH_WINDOW)
                n = int(len(residual))

                global_series = _numeric(work.loc[label_current].get(f"bias_correction_{metric}"), work.loc[label_current].index).fillna(0.0)
                global_correction = float(global_series.iloc[0]) if not global_series.empty else 0.0
                correction = global_correction
                if n >= LEASH_MIN_OBSERVATIONS:
                    segment_mean = float(residual.mean())
                    correction = float(
                        (n * segment_mean + LEASH_PRIOR_STRENGTH * global_correction)
                        / (n + LEASH_PRIOR_STRENGTH)
                    )
                    correction = float(np.clip(correction, -BIAS_CAPS[metric], BIAS_CAPS[metric]))

                workload_now = _numeric(work.loc[label_current].get(f"workload_{metric}"), work.loc[label_current].index)
                work.loc[label_current, f"leash_prior_n_{metric}"] = n
                work.loc[label_current, f"leash_correction_{metric}"] = correction
                work.loc[label_current, f"leash_candidate_{metric}"] = workload_now + correction

    return work.drop(columns=["_game_date_dt", "_leash_label"], errors="ignore")


def _metric_summary(frame: pd.DataFrame, metric: str) -> dict[str, object] | None:
    actual = _numeric(frame.get(f"actual_{metric}"), frame.index)
    workload = _numeric(frame.get(f"workload_{metric}"), frame.index)
    global_candidate = _numeric(frame.get(f"candidate_{metric}"), frame.index)
    leash_candidate = _numeric(frame.get(f"leash_candidate_{metric}"), frame.index)
    global_correction = _numeric(frame.get(f"bias_correction_{metric}"), frame.index).fillna(0.0)
    leash_correction = _numeric(frame.get(f"leash_correction_{metric}"), frame.index).fillna(0.0)

    ready = actual.notna() & workload.notna() & global_candidate.notna() & leash_candidate.notna()
    if not ready.any():
        return None

    a = actual[ready].astype(float)
    w = workload[ready].astype(float)
    g = global_candidate[ready].astype(float)
    l = leash_candidate[ready].astype(float)
    w_err = w - a
    g_err = g - a
    l_err = l - a
    w_mae = float(w_err.abs().mean())
    g_mae = float(g_err.abs().mean())
    l_mae = float(l_err.abs().mean())
    rel_vs_workload = float((w_mae - l_mae) / w_mae) if w_mae > 0 else float("nan")
    rel_vs_global = float((g_mae - l_mae) / g_mae) if g_mae > 0 else float("nan")

    changed = ready & (leash_correction - global_correction).abs().gt(1e-12)
    changed_n = int(changed.sum())
    if changed_n:
        l_changed_err = (leash_candidate[changed].astype(float) - actual[changed].astype(float)).abs()
        g_changed_err = (global_candidate[changed].astype(float) - actual[changed].astype(float)).abs()
        w_changed_err = (workload[changed].astype(float) - actual[changed].astype(float)).abs()
        win_vs_global = float((l_changed_err < g_changed_err).mean())
        win_vs_workload = float((l_changed_err < w_changed_err).mean())
    else:
        win_vs_global = win_vs_workload = float("nan")

    l_bias = float(l_err.mean())
    g_bias = float(g_err.mean())
    if changed_n < MIN_STATUS_STARTS:
        status = "LEARNING"
    elif rel_vs_global >= LEASH_MIN_RELATIVE_MAE and abs(l_bias) <= abs(g_bias) and win_vs_global >= 0.50:
        status = "HELPING"
    elif rel_vs_global <= -LEASH_MIN_RELATIVE_MAE and abs(l_bias) >= abs(g_bias) and win_vs_global <= 0.50:
        status = "HURTING"
    else:
        status = "MIXED"

    return {
        "Metric": metric.upper(),
        "Evaluated_Starts": int(ready.sum()),
        "Workload_v1_MAE": w_mae,
        "Global_v2_MAE": g_mae,
        "Leash_v21_MAE": l_mae,
        "Leash_v21_RMSE": float(np.sqrt(np.mean(np.square(l_err)))),
        "Global_v2_Bias": g_bias,
        "Leash_v21_Bias": l_bias,
        "Relative_MAE_vs_Workload_v1": rel_vs_workload,
        "Relative_MAE_vs_Global_v2": rel_vs_global,
        "Leash_Adjusted_Starts": changed_n,
        "Leash_Win_Share_vs_Workload_v1": win_vs_workload,
        "Leash_Win_Share_vs_Global_v2": win_vs_global,
        "Leash_Status": status,
        "Candidate_Version": LEASH_CANDIDATE_VERSION,
    }


def summarize_leash_candidate(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    work = frame if "leash_candidate_pitches" in frame.columns else attach_walk_forward_leash_candidate(frame)
    rows = [_metric_summary(work, metric) for metric in METRICS]
    return pd.DataFrame([row for row in rows if row is not None])


def leash_segment_report(frame: pd.DataFrame, min_starts: int = 15) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    work = frame if "leash_candidate_pitches" in frame.columns else attach_walk_forward_leash_candidate(frame)
    rows: list[dict[str, object]] = []
    for label, group in work.groupby(work.get("leash_label", pd.Series("UNKNOWN", index=work.index)).fillna("UNKNOWN").astype(str), dropna=False):
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
        candidate = attach_walk_forward_leash_candidate(detail)
        summary = summarize_leash_candidate(candidate)
        segment = leash_segment_report(candidate)
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
    parser = argparse.ArgumentParser(description="Cross-season report-only workload-v2.1 hierarchical leash validation.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--seasons", type=int, nargs="+", default=[2025, 2026])
    parser.add_argument("--summary", type=Path, default=Path("data/workload_v21_summary.csv"))
    parser.add_argument("--segments", type=Path, default=Path("data/workload_v21_segments.csv"))
    args = parser.parse_args()

    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    summary, segments = build_multi_season_report(history, [int(x) for x in args.seasons])
    if summary.empty:
        raise SystemExit("No workload-v2.1 validation rows were produced")
    for path in (args.summary, args.segments):
        path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary, index=False)
    segments.to_csv(args.segments, index=False)
    print(summary.to_string(index=False))
    print(f"seasons={sorted(summary['Season'].unique().tolist())} candidate={LEASH_CANDIDATE_VERSION}")


if __name__ == "__main__":
    main()
