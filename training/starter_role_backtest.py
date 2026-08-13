from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROLE_VERSION = "starter-role-backtest-v1.1"
ROLE_UNKNOWN = "UNKNOWN"
ROLE_ESTABLISHED = "ESTABLISHED"
ROLE_RAMPING = "RAMPING"
ROLE_RESTRICTED = "RESTRICTED"
ROLE_OPENER_LIKE = "OPENER_LIKE"
METRICS = ("pitches", "bf", "outs")
ACTUAL_COLUMNS = {"pitches": "actual_pitches", "bf": "actual_batters_faced", "outs": "actual_outs"}
PROJECTION_COLUMNS = {"pitches": "expected_pitches", "bf": "expected_bf", "outs": "expected_outs"}


def _num(s: object, index: pd.Index) -> pd.Series:
    if isinstance(s, pd.Series):
        return pd.to_numeric(s, errors="coerce")
    return pd.Series(np.nan, index=index, dtype=float)


def _role_from_prior(prior: pd.DataFrame) -> str:
    if len(prior) < 2:
        return ROLE_UNKNOWN
    prior = prior.tail(12)
    recent = prior.tail(min(3, len(prior)))
    earlier = prior.iloc[:-len(recent)].tail(5)
    rp = _num(recent.get("actual_pitches"), recent.index).dropna()
    ro = _num(recent.get("actual_outs"), recent.index).dropna()
    p = _num(prior.get("actual_pitches"), prior.index)
    bf = _num(prior.get("actual_batters_faced"), prior.index)
    outs = _num(prior.get("actual_outs"), prior.index)
    low = (p.le(55) | bf.le(14) | outs.le(9)).fillna(False)
    last3_low = low.tail(min(3, len(low)))
    if len(prior) >= 3 and int(last3_low.sum()) >= 2 and float(low.mean()) >= 0.50:
        return ROLE_OPENER_LIKE
    recent_p = float(rp.mean()) if not rp.empty else np.nan
    recent_o = float(ro.mean()) if not ro.empty else np.nan
    if np.isfinite(recent_p) and recent_p < 70 and (not np.isfinite(recent_o) or recent_o < 14):
        return ROLE_RESTRICTED
    ep = _num(earlier.get("actual_pitches"), earlier.index).dropna()
    prior_p = float(ep.mean()) if not ep.empty else np.nan
    if np.isfinite(recent_p) and np.isfinite(prior_p) and prior_p >= 55 and recent_p < 90 and recent_p / prior_p >= 1.15:
        return ROLE_RAMPING
    return ROLE_ESTABLISHED


def attach_roles(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame.copy()
    work = frame.copy()
    work["_dt"] = pd.to_datetime(work.get("game_date"), errors="coerce")
    work["starter_role_version"] = ROLE_VERSION
    work["starter_role_label"] = ROLE_UNKNOWN
    pitcher = work.get("pitcher_id", work.get("player_id", pd.Series(np.nan, index=work.index)))
    work["_pitcher"] = pitcher.astype(str)
    normalized = work["_dt"].dt.normalize()
    for date in sorted(normalized.dropna().drop_duplicates().tolist()):
        current = normalized.eq(date)
        for pid in work.loc[current, "_pitcher"].drop_duplicates():
            mask = current & work["_pitcher"].eq(pid)
            prior = work.loc[normalized.lt(date) & work["_pitcher"].eq(pid)].sort_values("_dt")
            work.loc[mask, "starter_role_label"] = _role_from_prior(prior)
    return work.drop(columns=["_dt", "_pitcher"], errors="ignore")


def summarize(frame: pd.DataFrame, min_starts: int = 20) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (season, role), group in frame.groupby(["season", "starter_role_label"], dropna=False):
        for metric in METRICS:
            actual = _num(group.get(ACTUAL_COLUMNS[metric]), group.index)
            baseline = _num(group.get(PROJECTION_COLUMNS[metric]), group.index)
            ready = actual.notna() & baseline.notna()
            n = int(ready.sum())
            if n < min_starts:
                continue
            err = baseline[ready].astype(float) - actual[ready].astype(float)
            rows.append({
                "Season": int(season), "Role": str(role), "Metric": metric.upper(), "Starts": n,
                "MAE": float(err.abs().mean()), "RMSE": float(np.sqrt(np.mean(np.square(err)))),
                "Bias": float(err.mean()), "Actual_Mean": float(actual[ready].mean()),
                "Projected_Mean": float(baseline[ready].mean()), "Role_Version": ROLE_VERSION,
            })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Chronological starter-role workload error segmentation.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/starter_role_segments.csv"))
    parser.add_argument("--seasons", type=int, nargs="+", default=[2024, 2025, 2026])
    args = parser.parse_args()
    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if history.empty:
        raise SystemExit("Projection log is empty")
    dates = pd.to_datetime(history.get("game_date"), errors="coerce")
    history = history.loc[dates.dt.year.isin(args.seasons)].copy()
    history["season"] = pd.to_datetime(history.get("game_date"), errors="coerce").dt.year
    report = summarize(attach_roles(history))
    if report.empty:
        raise SystemExit("No starter-role segment rows produced")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.output, index=False)
    print(report.to_string(index=False))


if __name__ == "__main__":
    main()
