from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from training.starter_role_backtest import (
    METRICS,
    ROLE_ESTABLISHED,
    ROLE_OPENER_LIKE,
    ROLE_RAMPING,
    ROLE_RESTRICTED,
    build_role_backtest,
)

# Report-only candidate fixed before replay. It does not assert injury/team intent.
# ROLE_RESTRICTED is treated literally as a low-recent-exposure state. Only
# RAMPING and low-recent-exposure starts are eligible. Corrections are learned
# from strictly earlier resolved starts with the same role, shrunk toward zero,
# and capped. ESTABLISHED and OPENER_LIKE starts are left untouched.
CANDIDATE_VERSION = "starter-role-workload-v1-candidate"
ELIGIBLE_ROLES = {ROLE_RAMPING, ROLE_RESTRICTED}
MIN_OBSERVATIONS = 30
WINDOW = 180
PRIOR_STRENGTH = 60.0
CAPS = {"pitches": 5.0, "bf": 1.5, "outs": 1.5}
MIN_STATUS_STARTS = 30
MIN_RELATIVE_MAE = 0.005


def _num(series: object, index: pd.Index) -> pd.Series:
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce")
    return pd.Series(np.nan, index=index, dtype=float)


def attach_role_candidate(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame.copy()
    work = frame.copy()
    work["_dt"] = pd.to_datetime(work.get("game_date"), errors="coerce")
    work["role_candidate_version"] = CANDIDATE_VERSION
    for metric in METRICS:
        baseline = _num(work.get(f"projected_{metric}"), work.index)
        work[f"role_prior_n_{metric}"] = 0
        work[f"role_correction_{metric}"] = 0.0
        work[f"role_candidate_{metric}"] = baseline.astype(float)

    normalized = work["_dt"].dt.normalize()
    for game_date in sorted(normalized.dropna().drop_duplicates().tolist()):
        current_date = normalized.eq(game_date)
        for role in ELIGIBLE_ROLES:
            current = current_date & work["starter_role_label"].eq(role)
            if not current.any():
                continue
            prior = work.loc[normalized.lt(game_date) & work["starter_role_label"].eq(role)]
            for metric in METRICS:
                actual = _num(prior.get(f"actual_{metric}"), prior.index)
                baseline = _num(prior.get(f"projected_{metric}"), prior.index)
                residual = (actual - baseline).dropna().tail(WINDOW)
                n = int(len(residual))
                correction = 0.0
                if n >= MIN_OBSERVATIONS:
                    shrink = float(n / (n + PRIOR_STRENGTH))
                    correction = float(np.clip(float(residual.mean()) * shrink, -CAPS[metric], CAPS[metric]))
                current_base = _num(work.loc[current].get(f"projected_{metric}"), work.loc[current].index)
                work.loc[current, f"role_prior_n_{metric}"] = n
                work.loc[current, f"role_correction_{metric}"] = correction
                work.loc[current, f"role_candidate_{metric}"] = current_base + correction
    return work.drop(columns=["_dt"], errors="ignore")


def summarize(frame: pd.DataFrame, min_starts: int = 20) -> pd.DataFrame:
    work = frame if "role_candidate_pitches" in frame.columns else attach_role_candidate(frame)
    rows: list[dict[str, object]] = []
    for (season, role), group in work.groupby(["season", "starter_role_label"], dropna=False):
        for metric in METRICS:
            actual = _num(group.get(f"actual_{metric}"), group.index)
            baseline = _num(group.get(f"projected_{metric}"), group.index)
            candidate = _num(group.get(f"role_candidate_{metric}"), group.index)
            correction = _num(group.get(f"role_correction_{metric}"), group.index).fillna(0.0)
            ready = actual.notna() & baseline.notna() & candidate.notna()
            n = int(ready.sum())
            if n < int(min_starts):
                continue
            a = actual[ready].astype(float)
            b = baseline[ready].astype(float)
            c = candidate[ready].astype(float)
            b_err = b - a
            c_err = c - a
            b_mae = float(b_err.abs().mean())
            c_mae = float(c_err.abs().mean())
            rel = float((b_mae - c_mae) / b_mae) if b_mae > 0 else float("nan")
            changed = ready & correction.abs().gt(1e-12)
            changed_n = int(changed.sum())
            win = float(((candidate[changed] - actual[changed]).abs() < (baseline[changed] - actual[changed]).abs()).mean()) if changed_n else float("nan")
            b_bias = float(b_err.mean())
            c_bias = float(c_err.mean())
            if changed_n < MIN_STATUS_STARTS:
                status = "LEARNING"
            elif rel >= MIN_RELATIVE_MAE and abs(c_bias) <= abs(b_bias) and win >= 0.50:
                status = "HELPING"
            elif rel <= -MIN_RELATIVE_MAE and abs(c_bias) >= abs(b_bias) and win <= 0.50:
                status = "HURTING"
            else:
                status = "MIXED"
            display_role = "LOW_RECENT_EXPOSURE" if str(role) == ROLE_RESTRICTED else str(role)
            rows.append({
                "Season": int(season),
                "Role": display_role,
                "Metric": metric.upper(),
                "Starts": n,
                "Adjusted_Starts": changed_n,
                "Baseline_MAE": b_mae,
                "Candidate_MAE": c_mae,
                "Baseline_RMSE": float(np.sqrt(np.mean(np.square(b_err)))),
                "Candidate_RMSE": float(np.sqrt(np.mean(np.square(c_err)))),
                "Baseline_Bias": b_bias,
                "Candidate_Bias": c_bias,
                "Relative_MAE": rel,
                "Win_Share": win,
                "Status": status,
                "Candidate_Version": CANDIDATE_VERSION,
            })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report-only starter-role workload candidate replay.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/starter_role_candidate_summary.csv"))
    parser.add_argument("--seasons", type=int, nargs="+", default=[2024, 2025, 2026])
    args = parser.parse_args()
    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if history.empty:
        raise SystemExit("Projection log is empty")
    detail = build_role_backtest(history, [int(s) for s in args.seasons])
    report = summarize(attach_role_candidate(detail))
    if report.empty:
        raise SystemExit("No starter-role candidate rows produced")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.output, index=False)
    print(report.to_string(index=False))
    print(f"candidate={CANDIDATE_VERSION} evaluated_starts={len(detail)}")


if __name__ == "__main__":
    main()
