from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from training.workload_backtest import build_backtest
from training.workload_leash_backtest import attach_walk_forward_leash_candidate

# Report-only workload-v2.4 candidate, fixed before the 2024-2026 replay.
# NORMAL/LONG remain global workload-v2. TIGHT begins with zero leash exposure.
# Exposure is earned only after enough strictly earlier TIGHT starts show that
# the leash delta points against (rather than reinforces) global-v2 bias. The
# learned bias-neutral weight is shrunk toward zero and capped in [0, 1].
# Sportsbook prices, bets, same-day outcomes, and future outcomes are excluded.
STABILIZED_VERSION = "workload-v2.4-direction-gated-tight-candidate"
TIGHT_LABEL = "TIGHT"
METRICS = ("pitches", "bf", "outs")
STABILIZED_MIN_OBSERVATIONS = 60
STABILIZED_WINDOW = 240
STABILIZED_PRIOR_STRENGTH = 120.0
STABILIZED_MIN_ABS_GLOBAL_BIAS = {"pitches": 0.20, "bf": 0.05, "outs": 0.05}
MIN_STATUS_STARTS = 30
MIN_RELATIVE_MAE = 0.0025


def _numeric(series: object, index: pd.Index | None = None) -> pd.Series:
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce")
    if index is None:
        return pd.Series(dtype=float)
    return pd.Series(np.nan, index=index, dtype=float)


def _earned_weight(global_error: pd.Series, leash_delta: pd.Series, metric: str) -> tuple[float, float, float, str]:
    ready = global_error.notna() & leash_delta.notna()
    if not ready.any():
        return 0.0, float("nan"), float("nan"), "NO_HISTORY"

    g = global_error[ready].tail(STABILIZED_WINDOW).astype(float)
    d = leash_delta[ready].tail(STABILIZED_WINDOW).astype(float)
    n = int(len(g))
    g_bias = float(g.mean())
    d_mean = float(d.mean())

    if n < STABILIZED_MIN_OBSERVATIONS:
        return 0.0, g_bias, d_mean, "INSUFFICIENT_HISTORY"
    if not np.isfinite(g_bias) or not np.isfinite(d_mean) or abs(d_mean) < 1e-9:
        return 0.0, g_bias, d_mean, "NO_DIRECTION"
    if abs(g_bias) < STABILIZED_MIN_ABS_GLOBAL_BIAS[metric]:
        return 0.0, g_bias, d_mean, "BIAS_ALREADY_SMALL"
    if g_bias * d_mean >= 0.0:
        return 0.0, g_bias, d_mean, "WRONG_DIRECTION"

    raw = float(np.clip(-g_bias / d_mean, 0.0, 1.0))
    shrink = float(n / (n + STABILIZED_PRIOR_STRENGTH))
    weight = float(np.clip(shrink * raw, 0.0, 1.0))
    return weight, g_bias, d_mean, "EARNED"


def attach_stabilized_tight_candidate(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach direction-gated TIGHT correction using strictly earlier dates."""
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame.copy()

    work = frame.copy()
    if "leash_candidate_pitches" not in work.columns:
        work = attach_walk_forward_leash_candidate(work)

    work["_game_date_dt"] = pd.to_datetime(work.get("game_date"), errors="coerce")
    work["_leash_label"] = work.get("leash_label", pd.Series("UNKNOWN", index=work.index)).fillna("UNKNOWN").astype(str)
    work["stabilized_version"] = STABILIZED_VERSION

    for metric in METRICS:
        global_candidate = _numeric(work.get(f"candidate_{metric}"), work.index)
        work[f"stabilized_prior_n_{metric}"] = 0
        work[f"stabilized_weight_{metric}"] = 0.0
        work[f"stabilized_prior_global_bias_{metric}"] = np.nan
        work[f"stabilized_prior_leash_delta_{metric}"] = np.nan
        work[f"stabilized_gate_{metric}"] = "GLOBAL_DEFAULT"
        work[f"stabilized_{metric}"] = global_candidate.astype(float)

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

            global_error = prior_global[ready] - prior_actual[ready]
            leash_delta = prior_leash[ready] - prior_global[ready]
            weight, g_bias, d_mean, gate = _earned_weight(global_error, leash_delta, metric)
            controlled = current_global + weight * (current_leash - current_global)

            work.loc[current_tight, f"stabilized_prior_n_{metric}"] = n
            work.loc[current_tight, f"stabilized_weight_{metric}"] = weight
            work.loc[current_tight, f"stabilized_prior_global_bias_{metric}"] = g_bias
            work.loc[current_tight, f"stabilized_prior_leash_delta_{metric}"] = d_mean
            work.loc[current_tight, f"stabilized_gate_{metric}"] = gate
            work.loc[current_tight, f"stabilized_{metric}"] = controlled

    return work.drop(columns=["_game_date_dt", "_leash_label"], errors="ignore")


def _metric_summary(frame: pd.DataFrame, metric: str) -> dict[str, object] | None:
    actual = _numeric(frame.get(f"actual_{metric}"), frame.index)
    workload = _numeric(frame.get(f"workload_{metric}"), frame.index)
    global_candidate = _numeric(frame.get(f"candidate_{metric}"), frame.index)
    stabilized = _numeric(frame.get(f"stabilized_{metric}"), frame.index)
    ready = actual.notna() & workload.notna() & global_candidate.notna() & stabilized.notna()
    if not ready.any():
        return None

    a = actual[ready].astype(float)
    w = workload[ready].astype(float)
    g = global_candidate[ready].astype(float)
    s = stabilized[ready].astype(float)
    w_err = w - a
    g_err = g - a
    s_err = s - a
    w_mae = float(w_err.abs().mean())
    g_mae = float(g_err.abs().mean())
    s_mae = float(s_err.abs().mean())
    rel_vs_workload = float((w_mae - s_mae) / w_mae) if w_mae > 0 else float("nan")
    rel_vs_global = float((g_mae - s_mae) / g_mae) if g_mae > 0 else float("nan")

    labels = frame.get("leash_label", pd.Series("UNKNOWN", index=frame.index)).fillna("UNKNOWN").astype(str)
    changed = ready & labels.eq(TIGHT_LABEL) & (stabilized - global_candidate).abs().gt(1e-12)
    changed_n = int(changed.sum())
    if changed_n:
        s_changed = (stabilized[changed].astype(float) - actual[changed].astype(float)).abs()
        g_changed = (global_candidate[changed].astype(float) - actual[changed].astype(float)).abs()
        w_changed = (workload[changed].astype(float) - actual[changed].astype(float)).abs()
        win_vs_global = float((s_changed < g_changed).mean())
        win_vs_workload = float((s_changed < w_changed).mean())
    else:
        win_vs_global = win_vs_workload = float("nan")

    g_bias = float(g_err.mean())
    s_bias = float(s_err.mean())
    if changed_n < MIN_STATUS_STARTS:
        status = "GUARDED"
    elif rel_vs_global >= MIN_RELATIVE_MAE and abs(s_bias) <= abs(g_bias) and win_vs_global >= 0.50:
        status = "HELPING"
    elif rel_vs_global <= -MIN_RELATIVE_MAE and abs(s_bias) >= abs(g_bias) and win_vs_global <= 0.50:
        status = "HURTING"
    else:
        status = "MIXED"

    weights = _numeric(frame.get(f"stabilized_weight_{metric}"), frame.index)
    tight_weights = weights[ready & labels.eq(TIGHT_LABEL) & weights.gt(0)]
    gates = frame.get(f"stabilized_gate_{metric}", pd.Series("UNKNOWN", index=frame.index)).astype(str)
    earned_n = int((ready & labels.eq(TIGHT_LABEL) & gates.eq("EARNED")).sum())
    guarded_n = int((ready & labels.eq(TIGHT_LABEL) & ~gates.eq("EARNED")).sum())
    return {
        "Metric": metric.upper(),
        "Evaluated_Starts": int(ready.sum()),
        "Workload_v1_MAE": w_mae,
        "Global_v2_MAE": g_mae,
        "Stabilized_v24_MAE": s_mae,
        "Stabilized_v24_RMSE": float(np.sqrt(np.mean(np.square(s_err)))),
        "Global_v2_Bias": g_bias,
        "Stabilized_v24_Bias": s_bias,
        "Relative_MAE_vs_Workload_v1": rel_vs_workload,
        "Relative_MAE_vs_Global_v2": rel_vs_global,
        "Stabilized_Adjusted_Starts": changed_n,
        "Stabilized_Win_Share_vs_Workload_v1": win_vs_workload,
        "Stabilized_Win_Share_vs_Global_v2": win_vs_global,
        "Mean_Earned_TIGHT_Weight": float(tight_weights.mean()) if not tight_weights.empty else float("nan"),
        "Earned_TIGHT_Starts": earned_n,
        "Guarded_TIGHT_Starts": guarded_n,
        "Stabilized_Status": status,
        "Candidate_Version": STABILIZED_VERSION,
    }


def summarize_stabilized_candidate(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    work = frame if "stabilized_pitches" in frame.columns else attach_stabilized_tight_candidate(frame)
    rows = [_metric_summary(work, metric) for metric in METRICS]
    return pd.DataFrame([row for row in rows if row is not None])


def segment_report(frame: pd.DataFrame, min_starts: int = 15) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    work = frame if "stabilized_pitches" in frame.columns else attach_stabilized_tight_candidate(frame)
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
        candidate = attach_stabilized_tight_candidate(detail)
        summary = summarize_stabilized_candidate(candidate)
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
    parser = argparse.ArgumentParser(description="Report-only workload-v2.4 direction-gated TIGHT validation.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--seasons", type=int, nargs="+", default=[2024, 2025, 2026])
    parser.add_argument("--summary", type=Path, default=Path("data/workload_v24_summary.csv"))
    parser.add_argument("--segments", type=Path, default=Path("data/workload_v24_segments.csv"))
    args = parser.parse_args()

    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    summary, segments = build_multi_season_report(history, [int(x) for x in args.seasons])
    if summary.empty:
        raise SystemExit("No workload-v2.4 validation rows were produced")
    for path in (args.summary, args.segments):
        path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary, index=False)
    segments.to_csv(args.segments, index=False)
    print(summary.to_string(index=False))
    print(f"seasons={sorted(summary['Season'].unique().tolist())} candidate={STABILIZED_VERSION}")


if __name__ == "__main__":
    main()
