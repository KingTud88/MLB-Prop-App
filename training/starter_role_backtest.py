from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from engine.workload_context import build_workload_context
from training.workload_backtest import fetch_pitcher_starts, tracked_pitcher_ids

# Historical role validation now uses the same MLB starter-only game-log source as
# the workload backtester. For every target start, role and workload context are
# reconstructed from strictly earlier starts only. Projection-log pitcher IDs are
# used only to define the tracked pitcher universe; sportsbook data is never used.
ROLE_VERSION = "starter-role-backtest-v2-mlb-history"
ROLE_UNKNOWN = "UNKNOWN"
ROLE_ESTABLISHED = "ESTABLISHED"
ROLE_RAMPING = "RAMPING"
ROLE_RESTRICTED = "RESTRICTED"
ROLE_OPENER_LIKE = "OPENER_LIKE"
METRICS = ("pitches", "bf", "outs")
MIN_PRIOR_STARTS = 2
MIN_REPORT_STARTS = 20


def _num(s: object, index: pd.Index) -> pd.Series:
    if isinstance(s, pd.Series):
        return pd.to_numeric(s, errors="coerce")
    return pd.Series(np.nan, index=index, dtype=float)


def _role_from_prior(prior: pd.DataFrame) -> str:
    if prior is None or len(prior) < MIN_PRIOR_STARTS:
        return ROLE_UNKNOWN
    prior = prior.sort_values("date").tail(12)
    recent = prior.tail(min(3, len(prior)))
    earlier = prior.iloc[:-len(recent)].tail(5)

    rp = _num(recent.get("pitches"), recent.index).dropna()
    ro = _num(recent.get("outs"), recent.index).dropna()
    p = _num(prior.get("pitches"), prior.index)
    bf = _num(prior.get("bf"), prior.index)
    outs = _num(prior.get("outs"), prior.index)
    low = (p.le(55) | bf.le(14) | outs.le(9)).fillna(False)
    last3_low = low.tail(min(3, len(low)))

    if len(prior) >= 3 and int(last3_low.sum()) >= 2 and float(low.mean()) >= 0.50:
        return ROLE_OPENER_LIKE

    recent_p = float(rp.mean()) if not rp.empty else np.nan
    recent_o = float(ro.mean()) if not ro.empty else np.nan
    if np.isfinite(recent_p) and recent_p < 70 and (not np.isfinite(recent_o) or recent_o < 14):
        return ROLE_RESTRICTED

    ep = _num(earlier.get("pitches"), earlier.index).dropna()
    prior_p = float(ep.mean()) if not ep.empty else np.nan
    if (
        np.isfinite(recent_p)
        and np.isfinite(prior_p)
        and prior_p >= 55
        and recent_p < 90
        and recent_p / prior_p >= 1.15
    ):
        return ROLE_RAMPING
    return ROLE_ESTABLISHED


def replay_pitcher_roles(starts: pd.DataFrame, target_seasons: set[int]) -> pd.DataFrame:
    if starts is None or starts.empty:
        return pd.DataFrame()
    data = starts.sort_values("date").reset_index(drop=True).copy()
    rows: list[dict[str, object]] = []
    for _, target in data.iterrows():
        season = int(target.get("season", 0) or 0)
        if season not in target_seasons:
            continue
        target_date = pd.Timestamp(target["date"])
        prior = data.loc[data["date"] < target_date].copy()
        role = _role_from_prior(prior)
        if role == ROLE_UNKNOWN:
            continue
        actual = {metric: float(target.get(metric)) for metric in METRICS}
        if not all(np.isfinite(v) for v in actual.values()):
            continue

        ctx = build_workload_context(prior[["date", "pitches", "bf", "outs"]], target_date)
        predictions = {
            "pitches": float(ctx.expected_pitches),
            "bf": float(ctx.expected_bf),
            "outs": float(ctx.expected_outs),
        }
        row: dict[str, object] = {
            "season": season,
            "pitcher_id": int(target["pitcher_id"]),
            "game_date": target_date.date().isoformat(),
            "starter_role_label": role,
            "prior_starts": int(len(prior)),
            "leash_label": ctx.leash_label,
        }
        for metric in METRICS:
            row[f"actual_{metric}"] = actual[metric]
            row[f"projected_{metric}"] = predictions[metric]
        rows.append(row)
    return pd.DataFrame(rows)


def build_role_backtest(
    projection_log: pd.DataFrame,
    seasons: list[int],
    session: requests.Session | None = None,
) -> pd.DataFrame:
    ids = tracked_pitcher_ids(projection_log)
    if not ids or not seasons:
        return pd.DataFrame()
    target_seasons = {int(s) for s in seasons}
    fetch_seasons = list(range(min(target_seasons) - 1, max(target_seasons) + 1))
    client = session or requests.Session()
    pieces: list[pd.DataFrame] = []
    for pitcher_id in ids:
        try:
            starts = fetch_pitcher_starts(pitcher_id, fetch_seasons, client)
        except requests.RequestException:
            continue
        replayed = replay_pitcher_roles(starts, target_seasons)
        if not replayed.empty:
            pieces.append(replayed)
    return pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()


def summarize(frame: pd.DataFrame, min_starts: int = MIN_REPORT_STARTS) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for (season, role), group in frame.groupby(["season", "starter_role_label"], dropna=False):
        for metric in METRICS:
            actual = _num(group.get(f"actual_{metric}"), group.index)
            projected = _num(group.get(f"projected_{metric}"), group.index)
            ready = actual.notna() & projected.notna()
            n = int(ready.sum())
            if n < int(min_starts):
                continue
            err = projected[ready].astype(float) - actual[ready].astype(float)
            rows.append({
                "Season": int(season),
                "Role": str(role),
                "Metric": metric.upper(),
                "Starts": n,
                "MAE": float(err.abs().mean()),
                "RMSE": float(np.sqrt(np.mean(np.square(err)))),
                "Bias": float(err.mean()),
                "Actual_Mean": float(actual[ready].mean()),
                "Projected_Mean": float(projected[ready].mean()),
                "Role_Version": ROLE_VERSION,
            })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="MLB-history chronological starter-role workload segmentation.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/starter_role_segments.csv"))
    parser.add_argument("--seasons", type=int, nargs="+", default=[2024, 2025, 2026])
    args = parser.parse_args()

    projection_log = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    if projection_log.empty:
        raise SystemExit("Projection log is empty")
    detail = build_role_backtest(projection_log, [int(s) for s in args.seasons])
    report = summarize(detail)
    if report.empty:
        raise SystemExit("No starter-role segment rows produced")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.output, index=False)
    print(report.to_string(index=False))
    print(f"evaluated_starts={len(detail)} role_version={ROLE_VERSION}")


if __name__ == "__main__":
    main()
