from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from training.workload_backtest import build_backtest
from training.workload_bias_controlled_backtest import attach_bias_controlled_tight_candidate

# Predeclared report-only v2.4 rule. v2.3 showed durable TIGHT MAE gains but
# retained negative TIGHT bias. v2.4 preserves the v2.3 candidate and adds a
# second, leakage-safe residual correction ONLY for TIGHT starts. The residual
# correction uses strictly earlier TIGHT v2.3 errors, requires 90 observations,
# uses a 240-start window, shrinks toward zero with 180 pseudo-observations, and
# is capped per metric. NORMAL/LONG remain exactly on global v2. No market,
# sportsbook, bet, same-day outcome, or future outcome data is used.
V24_VERSION = "workload-v2.4-tight-residual-bias-candidate"
TIGHT_LABEL = "TIGHT"
METRICS = ("pitches", "bf", "outs")
MIN_PRIOR = 90
WINDOW = 240
PRIOR_STRENGTH = 180.0
CAPS = {"pitches": 1.5, "bf": 0.5, "outs": 0.5}
MIN_STATUS_STARTS = 30
MIN_RELATIVE_MAE = 0.0025


def _numeric(series: object, index: pd.Index) -> pd.Series:
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce")
    return pd.Series(np.nan, index=index, dtype=float)


def attach_v24_candidate(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame.copy()
    work = frame.copy()
    if "bias_controlled_pitches" not in work.columns:
        work = attach_bias_controlled_tight_candidate(work)
    work["_date"] = pd.to_datetime(work.get("game_date"), errors="coerce").dt.normalize()
    labels = work.get("leash_label", pd.Series("UNKNOWN", index=work.index)).fillna("UNKNOWN").astype(str)
    work["_label"] = labels
    work["v24_version"] = V24_VERSION
    for metric in METRICS:
        v23 = _numeric(work.get(f"bias_controlled_{metric}"), work.index)
        work[f"v24_prior_n_{metric}"] = 0
        work[f"v24_residual_correction_{metric}"] = 0.0
        work[f"v24_candidate_{metric}"] = v23.astype(float)

    for game_date in sorted(work["_date"].dropna().drop_duplicates().tolist()):
        current = work["_date"].eq(game_date) & work["_label"].eq(TIGHT_LABEL)
        if not current.any():
            continue
        prior_mask = work["_date"].lt(game_date) & work["_label"].eq(TIGHT_LABEL)
        prior = work.loc[prior_mask]
        for metric in METRICS:
            actual = _numeric(prior.get(f"actual_{metric}"), prior.index)
            v23_prior = _numeric(prior.get(f"bias_controlled_{metric}"), prior.index)
            residual = (actual - v23_prior).dropna().tail(WINDOW)
            n = int(len(residual))
            correction = 0.0
            if n >= MIN_PRIOR:
                mean_residual = float(residual.mean())
                correction = float(n * mean_residual / (n + PRIOR_STRENGTH))
                correction = float(np.clip(correction, -CAPS[metric], CAPS[metric]))
            v23_now = _numeric(work.loc[current].get(f"bias_controlled_{metric}"), work.loc[current].index)
            work.loc[current, f"v24_prior_n_{metric}"] = n
            work.loc[current, f"v24_residual_correction_{metric}"] = correction
            work.loc[current, f"v24_candidate_{metric}"] = v23_now + correction
    return work.drop(columns=["_date", "_label"], errors="ignore")


def _summary(frame: pd.DataFrame, metric: str) -> dict[str, object] | None:
    actual = _numeric(frame.get(f"actual_{metric}"), frame.index)
    global_v2 = _numeric(frame.get(f"candidate_{metric}"), frame.index)
    v23 = _numeric(frame.get(f"bias_controlled_{metric}"), frame.index)
    v24 = _numeric(frame.get(f"v24_candidate_{metric}"), frame.index)
    ready = actual.notna() & global_v2.notna() & v23.notna() & v24.notna()
    if not ready.any():
        return None
    a, g, b, c = (x[ready].astype(float) for x in (actual, global_v2, v23, v24))
    gerr, berr, cerr = g-a, b-a, c-a
    gmae, bmae, cmae = float(gerr.abs().mean()), float(berr.abs().mean()), float(cerr.abs().mean())
    rel_global = (gmae-cmae)/gmae if gmae else float("nan")
    rel_v23 = (bmae-cmae)/bmae if bmae else float("nan")
    labels = frame.get("leash_label", pd.Series("UNKNOWN", index=frame.index)).fillna("UNKNOWN").astype(str)
    changed = ready & labels.eq(TIGHT_LABEL) & (v24-v23).abs().gt(1e-12)
    n = int(changed.sum())
    win = float(((v24[changed]-actual[changed]).abs() < (v23[changed]-actual[changed]).abs()).mean()) if n else float("nan")
    gbias, bbias, cbias = float(gerr.mean()), float(berr.mean()), float(cerr.mean())
    if n < MIN_STATUS_STARTS:
        status = "LEARNING"
    elif rel_v23 >= MIN_RELATIVE_MAE and abs(cbias) <= abs(bbias) and win >= 0.50:
        status = "HELPING"
    elif rel_v23 <= -MIN_RELATIVE_MAE and abs(cbias) >= abs(bbias) and win <= 0.50:
        status = "HURTING"
    else:
        status = "MIXED"
    return {"Metric":metric.upper(),"Evaluated_Starts":int(ready.sum()),"Global_v2_MAE":gmae,"V23_MAE":bmae,"V24_MAE":cmae,"Global_v2_Bias":gbias,"V23_Bias":bbias,"V24_Bias":cbias,"Relative_MAE_vs_Global_v2":rel_global,"Relative_MAE_vs_v23":rel_v23,"V24_Adjusted_Starts":n,"V24_Win_Share_vs_v23":win,"V24_Status":status,"Candidate_Version":V24_VERSION}


def reports(log: pd.DataFrame, seasons: list[int]) -> tuple[pd.DataFrame,pd.DataFrame]:
    overall=[]; segments=[]
    for season in seasons:
        detail=build_backtest(log,target_season=season)
        if detail.empty: continue
        cand=attach_v24_candidate(detail)
        for metric in METRICS:
            row=_summary(cand,metric)
            if row: overall.append({"Season":season,**row})
        labels=cand.get("leash_label",pd.Series("UNKNOWN",index=cand.index)).fillna("UNKNOWN").astype(str)
        for label,group in cand.groupby(labels):
            for metric in METRICS:
                row=_summary(group,metric)
                if row and int(row["Evaluated_Starts"])>=15: segments.append({"Season":season,"Leash":str(label),**row})
    return pd.DataFrame(overall),pd.DataFrame(segments)


def main() -> None:
    p=argparse.ArgumentParser(description="Report-only workload v2.4 TIGHT residual-bias replay")
    p.add_argument("--projection-log",type=Path,default=Path("data/projection_log.csv"))
    p.add_argument("--seasons",type=int,nargs="+",default=[2024,2025,2026])
    p.add_argument("--summary",type=Path,default=Path("data/workload_v24_summary.csv"))
    p.add_argument("--segments",type=Path,default=Path("data/workload_v24_segments.csv"))
    a=p.parse_args(); log=pd.read_csv(a.projection_log) if a.projection_log.exists() else pd.DataFrame()
    summary,segments=reports(log,[int(x) for x in a.seasons])
    if summary.empty: raise SystemExit("No workload-v2.4 rows produced")
    a.summary.parent.mkdir(parents=True,exist_ok=True); a.segments.parent.mkdir(parents=True,exist_ok=True)
    summary.to_csv(a.summary,index=False); segments.to_csv(a.segments,index=False)
    print(summary.to_string(index=False))

if __name__=="__main__": main()
