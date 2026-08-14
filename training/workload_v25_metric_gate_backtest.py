from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from training.workload_backtest import build_backtest
from training.workload_v24_backtest import attach_v24_candidate

# Report-only v2.5 rule, fixed before this replay. The v2.4 residual correction
# is NOT accepted blindly. For each TIGHT metric and game date, v2.4 is allowed
# only when strictly earlier TIGHT rows where v2.4 actually differed from v2.3
# show all three: >=0.25% MAE improvement vs v2.3, no worse absolute bias, and
# >=50% win share. Otherwise that metric stays on v2.3. NORMAL/LONG remain on
# global v2 through the inherited v2.3/v2.4 construction. Same-day outcomes,
# future outcomes, sportsbook prices, and bet history are excluded.
V25_VERSION = "workload-v2.5-tight-metric-evidence-gate"
TIGHT_LABEL = "TIGHT"
METRICS = ("pitches", "bf", "outs")
GATE_MIN_CHANGED = 60
GATE_WINDOW = 180
GATE_MIN_RELATIVE_MAE = 0.0025
GATE_MIN_WIN_SHARE = 0.50
MIN_STATUS_STARTS = 30
MIN_RELATIVE_MAE = 0.0025


def _numeric(series: object, index: pd.Index) -> pd.Series:
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce")
    return pd.Series(np.nan, index=index, dtype=float)


def _prior_gate(prior: pd.DataFrame, metric: str) -> tuple[bool, int, float, float, float, str]:
    actual = _numeric(prior.get(f"actual_{metric}"), prior.index)
    v23 = _numeric(prior.get(f"bias_controlled_{metric}"), prior.index)
    v24 = _numeric(prior.get(f"v24_candidate_{metric}"), prior.index)
    ready = actual.notna() & v23.notna() & v24.notna() & (v24 - v23).abs().gt(1e-12)
    rows = prior.loc[ready].tail(GATE_WINDOW)
    n = int(len(rows))
    if n < GATE_MIN_CHANGED:
        return False, n, float("nan"), float("nan"), float("nan"), "INSUFFICIENT_CHANGED_HISTORY"

    a = _numeric(rows.get(f"actual_{metric}"), rows.index).astype(float)
    b = _numeric(rows.get(f"bias_controlled_{metric}"), rows.index).astype(float)
    c = _numeric(rows.get(f"v24_candidate_{metric}"), rows.index).astype(float)
    b_err = b - a
    c_err = c - a
    b_mae = float(b_err.abs().mean())
    c_mae = float(c_err.abs().mean())
    rel = float((b_mae - c_mae) / b_mae) if b_mae > 0 else float("nan")
    win = float((c_err.abs() < b_err.abs()).mean())
    b_bias = float(b_err.mean())
    c_bias = float(c_err.mean())

    reasons: list[str] = []
    if not np.isfinite(rel) or rel < GATE_MIN_RELATIVE_MAE:
        reasons.append("MAE")
    if abs(c_bias) > abs(b_bias):
        reasons.append("BIAS")
    if win < GATE_MIN_WIN_SHARE:
        reasons.append("WIN_SHARE")
    if reasons:
        return False, n, rel, b_bias, c_bias, "FAIL_" + "_".join(reasons)
    return True, n, rel, b_bias, c_bias, "EARNED"


def attach_v25_candidate(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame.copy()
    work = frame.copy()
    if "v24_candidate_pitches" not in work.columns:
        work = attach_v24_candidate(work)

    work["_date"] = pd.to_datetime(work.get("game_date"), errors="coerce").dt.normalize()
    labels = work.get("leash_label", pd.Series("UNKNOWN", index=work.index)).fillna("UNKNOWN").astype(str)
    work["_label"] = labels
    work["v25_version"] = V25_VERSION

    for metric in METRICS:
        v23 = _numeric(work.get(f"bias_controlled_{metric}"), work.index)
        work[f"v25_candidate_{metric}"] = v23.astype(float)
        work[f"v25_gate_{metric}"] = "V23_DEFAULT"
        work[f"v25_gate_prior_n_{metric}"] = 0
        work[f"v25_gate_prior_rel_mae_{metric}"] = np.nan
        work[f"v25_gate_prior_v23_bias_{metric}"] = np.nan
        work[f"v25_gate_prior_v24_bias_{metric}"] = np.nan

    for game_date in sorted(work["_date"].dropna().drop_duplicates().tolist()):
        current = work["_date"].eq(game_date) & work["_label"].eq(TIGHT_LABEL)
        if not current.any():
            continue
        prior = work.loc[work["_date"].lt(game_date) & work["_label"].eq(TIGHT_LABEL)]
        for metric in METRICS:
            earned, n, rel, v23_bias, v24_bias, gate = _prior_gate(prior, metric)
            if earned:
                chosen = _numeric(work.loc[current].get(f"v24_candidate_{metric}"), work.loc[current].index)
            else:
                chosen = _numeric(work.loc[current].get(f"bias_controlled_{metric}"), work.loc[current].index)
            work.loc[current, f"v25_candidate_{metric}"] = chosen
            work.loc[current, f"v25_gate_{metric}"] = gate
            work.loc[current, f"v25_gate_prior_n_{metric}"] = n
            work.loc[current, f"v25_gate_prior_rel_mae_{metric}"] = rel
            work.loc[current, f"v25_gate_prior_v23_bias_{metric}"] = v23_bias
            work.loc[current, f"v25_gate_prior_v24_bias_{metric}"] = v24_bias

    return work.drop(columns=["_date", "_label"], errors="ignore")


def _summary(frame: pd.DataFrame, metric: str) -> dict[str, object] | None:
    actual = _numeric(frame.get(f"actual_{metric}"), frame.index)
    global_v2 = _numeric(frame.get(f"candidate_{metric}"), frame.index)
    v23 = _numeric(frame.get(f"bias_controlled_{metric}"), frame.index)
    v25 = _numeric(frame.get(f"v25_candidate_{metric}"), frame.index)
    ready = actual.notna() & global_v2.notna() & v23.notna() & v25.notna()
    if not ready.any():
        return None

    a = actual[ready].astype(float)
    g = global_v2[ready].astype(float)
    b = v23[ready].astype(float)
    c = v25[ready].astype(float)
    gerr, berr, cerr = g-a, b-a, c-a
    gmae, bmae, cmae = float(gerr.abs().mean()), float(berr.abs().mean()), float(cerr.abs().mean())
    rel_global = float((gmae-cmae)/gmae) if gmae else float("nan")
    rel_v23 = float((bmae-cmae)/bmae) if bmae else float("nan")

    labels = frame.get("leash_label", pd.Series("UNKNOWN", index=frame.index)).fillna("UNKNOWN").astype(str)
    changed = ready & labels.eq(TIGHT_LABEL) & (v25-v23).abs().gt(1e-12)
    n = int(changed.sum())
    win = float(((v25[changed]-actual[changed]).abs() < (v23[changed]-actual[changed]).abs()).mean()) if n else float("nan")
    gbias, bbias, cbias = float(gerr.mean()), float(berr.mean()), float(cerr.mean())

    if n < MIN_STATUS_STARTS:
        status = "GUARDED"
    elif rel_v23 >= MIN_RELATIVE_MAE and abs(cbias) <= abs(bbias) and win >= 0.50:
        status = "HELPING"
    elif rel_v23 <= -MIN_RELATIVE_MAE and abs(cbias) >= abs(bbias) and win <= 0.50:
        status = "HURTING"
    else:
        status = "MIXED"

    gates = frame.get(f"v25_gate_{metric}", pd.Series("UNKNOWN", index=frame.index)).astype(str)
    earned_n = int((ready & labels.eq(TIGHT_LABEL) & gates.eq("EARNED")).sum())
    guarded_n = int((ready & labels.eq(TIGHT_LABEL) & ~gates.eq("EARNED")).sum())
    return {
        "Metric": metric.upper(),
        "Evaluated_Starts": int(ready.sum()),
        "Global_v2_MAE": gmae,
        "V23_MAE": bmae,
        "V25_MAE": cmae,
        "Global_v2_Bias": gbias,
        "V23_Bias": bbias,
        "V25_Bias": cbias,
        "Relative_MAE_vs_Global_v2": rel_global,
        "Relative_MAE_vs_v23": rel_v23,
        "V25_Adjusted_Starts": n,
        "V25_Win_Share_vs_v23": win,
        "Earned_TIGHT_Starts": earned_n,
        "Guarded_TIGHT_Starts": guarded_n,
        "V25_Status": status,
        "Candidate_Version": V25_VERSION,
    }


def reports(log: pd.DataFrame, seasons: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    overall: list[dict[str, object]] = []
    segments: list[dict[str, object]] = []
    for season in seasons:
        detail = build_backtest(log, target_season=int(season))
        if detail.empty:
            continue
        cand = attach_v25_candidate(detail)
        for metric in METRICS:
            row = _summary(cand, metric)
            if row:
                overall.append({"Season": int(season), **row})
        labels = cand.get("leash_label", pd.Series("UNKNOWN", index=cand.index)).fillna("UNKNOWN").astype(str)
        for label, group in cand.groupby(labels):
            for metric in METRICS:
                row = _summary(group, metric)
                if row and int(row["Evaluated_Starts"]) >= 15:
                    segments.append({"Season": int(season), "Leash": str(label), **row})
    return pd.DataFrame(overall), pd.DataFrame(segments)


def main() -> None:
    p = argparse.ArgumentParser(description="Report-only workload-v2.5 metric-evidence-gated TIGHT replay")
    p.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    p.add_argument("--seasons", type=int, nargs="+", default=[2024, 2025, 2026])
    p.add_argument("--summary", type=Path, default=Path("data/workload_v25_summary.csv"))
    p.add_argument("--segments", type=Path, default=Path("data/workload_v25_segments.csv"))
    a = p.parse_args()
    log = pd.read_csv(a.projection_log) if a.projection_log.exists() else pd.DataFrame()
    summary, segments = reports(log, [int(x) for x in a.seasons])
    if summary.empty:
        raise SystemExit("No workload-v2.5 rows produced")
    a.summary.parent.mkdir(parents=True, exist_ok=True)
    a.segments.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(a.summary, index=False)
    segments.to_csv(a.segments, index=False)
    print(summary.to_string(index=False))

if __name__ == "__main__":
    main()
