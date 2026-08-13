from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from training.workload_backtest import build_backtest
from training.workload_leash_backtest import attach_walk_forward_leash_candidate

# Report-only workload-v2.3 candidate. This rule was fixed before its 2024-2026
# replay: NORMAL/LONG stay on the global v2 correction. TIGHT starts receive a
# conservative blend between global v2 and the hierarchical leash candidate.
# The blend can move only from strictly earlier TIGHT starts and is shrunk hard
# toward 50%. Sportsbook prices, bets, same-day outcomes, and future outcomes
# are never inputs.
BIAS_CONTROLLED_VERSION = "workload-v2.3-bias-controlled-tight-candidate"
TIGHT_LABEL = "TIGHT"
METRICS = ("pitches", "bf", "outs")
BIAS_CONTROL_MIN_OBSERVATIONS = 60
BIAS_CONTROL_WINDOW = 240
BIAS_CONTROL_PRIOR_WEIGHT = 0.50
BIAS_CONTROL_PRIOR_STRENGTH = 120.0
MIN_STATUS_STARTS = 30
MIN_RELATIVE_MAE = 0.0025


def _numeric(series: object, index: pd.Index | None = None) -> pd.Series:
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce")
    if index is None:
        return pd.Series(dtype=float)
    return pd.Series(np.nan, index=index, dtype=float)


def _bias_neutral_weight(global_error: pd.Series, leash_delta: pd.Series) -> float:
    ready = global_error.notna() & leash_delta.notna()
    if not ready.any():
        return BIAS_CONTROL_PRIOR_WEIGHT
    g_bias = float(global_error[ready].tail(BIAS_CONTROL_WINDOW).mean())
    d_mean = float(leash_delta[ready].tail(BIAS_CONTROL_WINDOW).mean())
    if not np.isfinite(g_bias) or not np.isfinite(d_mean) or abs(d_mean) < 1e-9:
        return BIAS_CONTROL_PRIOR_WEIGHT
    raw = float(np.clip(-g_bias / d_mean, 0.0, 1.0))
    n = int(min(int(ready.sum()), BIAS_CONTROL_WINDOW))
    shrink = float(n / (n + BIAS_CONTROL_PRIOR_STRENGTH))
    return float(BIAS_CONTROL_PRIOR_WEIGHT + shrink * (raw - BIAS_CONTROL_PRIOR_WEIGHT))


def attach_bias_controlled_tight_candidate(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach leakage-safe TIGHT-only bias control using strictly earlier dates."""
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame.copy()

    work = frame.copy()
    if "leash_candidate_pitches" not in work.columns:
        work = attach_walk_forward_leash_candidate(work)

    work["_game_date_dt"] = pd.to_datetime(work.get("game_date"), errors="coerce")
    labels = work.get("leash_label", pd.Series("UNKNOWN", index=work.index)).fillna("UNKNOWN").astype(str)
    work["_leash_label"] = labels
    work["bias_controlled_version"] = BIAS_CONTROLLED_VERSION

    for metric in METRICS:
        global_candidate = _numeric(work.get(f"candidate_{metric}"), work.index)
        work[f"bias_control_prior_n_{metric}"] = 0
        work[f"bias_control_weight_{metric}"] = 0.0
        work[f"bias_controlled_{metric}"] = global_candidate.astype(float)

    normalized = work["_game_date_dt"].dt.normalize()
    for game_date in sorted(normalized.dropna().drop_duplicates().tolist()):
        current_tight = normalized.eq(game_date) & work["_leash_label"].eq(TIGHT_LABEL)
        if not current_tight.any():
            continue
        prior_tight = normalized.lt(game_date) & work["_leash_label"].eq(TIGHT_LABEL)
        prior = work.loc[prior_tight]

        for metric in METRICS:
            current_global = _numeric(work.loc[current_tight].get(f"candidate_{metric}"), work.loc[current_tight].index)
            current_leash = _numeric(work.loc[current_tight].get(f"leash_candidate_{metric}"), work.loc[current_tight].index)
            prior_actual = _numeric(prior.get(f"actual_{metric}"), prior.index)
            prior_global = _numeric(prior.get(f"candidate_{metric}"), prior.index)
            prior_leash = _numeric(prior.get(f"leash_candidate_{metric}"), prior.index)
            ready = prior_actual.notna() & prior_global.notna() & prior_leash.notna()
            n = int(ready.sum())

            # The leash candidate itself does not diverge from global until its
            # own minimum sample is met. Once it does, start with a fixed 50%
            # shrink. At 60+ strictly prior TIGHT observations, the weight may
            # move toward the bias-neutral value learned from prior residuals.
            weight = BIAS_CONTROL_PRIOR_WEIGHT if n > 0 else 0.0
            if n >= BIAS_CONTROL_MIN_OBSERVATIONS:
                global_error = (prior_global[ready] - prior_actual[ready]).tail(BIAS_CONTROL_WINDOW)
                leash_delta = (prior_leash[ready] - prior_global[ready]).tail(BIAS_CONTROL_WINDOW)
                weight = _bias_neutral_weight(global_error, leash_delta)

            delta_now = current_leash - current_global
            controlled = current_global + float(weight) * delta_now
            work.loc[current_tight, f"bias_control_prior_n_{metric}"] = n
            work.loc[current_tight, f"bias_control_weight_{metric}"] = float(weight)
            work.loc[current_tight, f"bias_controlled_{metric}"] = controlled

    return work.drop(columns=["_game_date_dt", "_leash_label"], errors="ignore")


def _metric_summary(frame: pd.DataFrame, metric: str) -> dict[str, object] | None:
    actual = _numeric(frame.get(f"actual_{metric}"), frame.index)
    workload = _numeric(frame.get(f"workload_{metric}"), frame.index)
    global_candidate = _numeric(frame.get(f"candidate_{metric}"), frame.index)
    controlled = _numeric(frame.get(f"bias_controlled_{metric}"), frame.index)
    ready = actual.notna() & workload.notna() & global_candidate.notna() & controlled.notna()
    if not ready.any():
        return None

    a = actual[ready].astype(float)
    w = workload[ready].astype(float)
    g = global_candidate[ready].astype(float)
    c = controlled[ready].astype(float)
    w_err = w - a
    g_err = g - a
    c_err = c - a
    w_mae = float(w_err.abs().mean())
    g_mae = float(g_err.abs().mean())
    c_mae = float(c_err.abs().mean())
    rel_vs_workload = float((w_mae - c_mae) / w_mae) if w_mae > 0 else float("nan")
    rel_vs_global = float((g_mae - c_mae) / g_mae) if g_mae > 0 else float("nan")

    labels = frame.get("leash_label", pd.Series("UNKNOWN", index=frame.index)).fillna("UNKNOWN").astype(str)
    changed = ready & labels.eq(TIGHT_LABEL) & (controlled - global_candidate).abs().gt(1e-12)
    changed_n = int(changed.sum())
    if changed_n:
        c_changed = (controlled[changed].astype(float) - actual[changed].astype(float)).abs()
        g_changed = (global_candidate[changed].astype(float) - actual[changed].astype(float)).abs()
        w_changed = (workload[changed].astype(float) - actual[changed].astype(float)).abs()
        win_vs_global = float((c_changed < g_changed).mean())
        win_vs_workload = float((c_changed < w_changed).mean())
    else:
        win_vs_global = win_vs_workload = float("nan")

    g_bias = float(g_err.mean())
    c_bias = float(c_err.mean())
    if changed_n < MIN_STATUS_STARTS:
        status = "LEARNING"
    elif rel_vs_global >= MIN_RELATIVE_MAE and abs(c_bias) <= abs(g_bias) and win_vs_global >= 0.50:
        status = "HELPING"
    elif rel_vs_global <= -MIN_RELATIVE_MAE and abs(c_bias) >= abs(g_bias) and win_vs_global <= 0.50:
        status = "HURTING"
    else:
        status = "MIXED"

    weights = _numeric(frame.get(f"bias_control_weight_{metric}"), frame.index)
    tight_weights = weights[ready & labels.eq(TIGHT_LABEL) & weights.gt(0)]
    return {
        "Metric": metric.upper(),
        "Evaluated_Starts": int(ready.sum()),
        "Workload_v1_MAE": w_mae,
        "Global_v2_MAE": g_mae,
        "BiasControlled_v23_MAE": c_mae,
        "BiasControlled_v23_RMSE": float(np.sqrt(np.mean(np.square(c_err)))),
        "Global_v2_Bias": g_bias,
        "BiasControlled_v23_Bias": c_bias,
        "Relative_MAE_vs_Workload_v1": rel_vs_workload,
        "Relative_MAE_vs_Global_v2": rel_vs_global,
        "BiasControlled_Adjusted_Starts": changed_n,
        "BiasControlled_Win_Share_vs_Workload_v1": win_vs_workload,
        "BiasControlled_Win_Share_vs_Global_v2": win_vs_global,
        "Mean_TIGHT_Weight": float(tight_weights.mean()) if not tight_weights.empty else float("nan"),
        "BiasControlled_Status": status,
        "Candidate_Version": BIAS_CONTROLLED_VERSION,
    }


def summarize_bias_controlled_candidate(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    work = frame if "bias_controlled_pitches" in frame.columns else attach_bias_controlled_tight_candidate(frame)
    rows = [_metric_summary(work, metric) for metric in METRICS]
    return pd.DataFrame([row for row in rows if row is not None])


def segment_report(frame: pd.DataFrame, min_starts: int = 15) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    work = frame if "bias_controlled_pitches" in frame.columns else attach_bias_controlled_tight_candidate(frame)
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
        candidate = attach_bias_controlled_tight_candidate(detail)
        summary = summarize_bias_controlled_candidate(candidate)
        segment = segment_report(candidate)
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
    parser = argparse.ArgumentParser(description="Report-only workload-v2.3 bias-controlled TIGHT validation.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--seasons", type=int, nargs="+", default=[2024, 2025, 2026])
    parser.add_argument("--summary", type=Path, default=Path("data/workload_v23_summary.csv"))
    parser.add_argument("--segments", type=Path, default=Path("data/workload_v23_segments.csv"))
    args = parser.parse_args()

    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    summary, segments = build_multi_season_report(history, [int(x) for x in args.seasons])
    if summary.empty:
        raise SystemExit("No workload-v2.3 validation rows were produced")
    for path in (args.summary, args.segments):
        path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary, index=False)
    segments.to_csv(args.segments, index=False)
    print(summary.to_string(index=False))
    print(f"seasons={sorted(summary['Season'].unique().tolist())} candidate={BIAS_CONTROLLED_VERSION}")


if __name__ == "__main__":
    main()
