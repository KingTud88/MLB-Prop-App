from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import requests

from engine.workload_context import WORKLOAD_VERSION, build_workload_context

MLB_API = "https://statsapi.mlb.com/api/v1"
MIN_PRIOR_STARTS = 3
MIN_STATUS_STARTS = 30


def _parse_outs(value: object) -> float:
    try:
        text = str(value)
        whole, frac = text.split(".", 1)
        return float(int(whole) * 3 + int(frac[:1]))
    except Exception:
        return float("nan")


def _numeric(value: object) -> float:
    try:
        out = float(value)
        return out if np.isfinite(out) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def tracked_pitcher_ids(projection_log: pd.DataFrame) -> list[int]:
    if projection_log is None or projection_log.empty or "pitcher_id" not in projection_log.columns:
        return []
    ids = pd.to_numeric(projection_log["pitcher_id"], errors="coerce").dropna().astype(int)
    return sorted({int(x) for x in ids if int(x) > 0})


def fetch_pitcher_starts(
    pitcher_id: int,
    seasons: Iterable[int],
    session: requests.Session | None = None,
) -> pd.DataFrame:
    client = session or requests.Session()
    rows: list[dict[str, object]] = []
    for season in seasons:
        response = client.get(
            f"{MLB_API}/people/{int(pitcher_id)}/stats",
            params={"stats": "gameLog", "group": "pitching", "season": int(season), "gameType": "R"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        for block in payload.get("stats", []) or []:
            for split in block.get("splits", []) or []:
                stat = split.get("stat", {}) or {}
                if int(float(stat.get("gamesStarted", 0) or 0)) <= 0:
                    continue
                rows.append(
                    {
                        "pitcher_id": int(pitcher_id),
                        "date": pd.to_datetime(split.get("date"), errors="coerce"),
                        "season": int(season),
                        "pitches": _numeric(stat.get("numberOfPitches")),
                        "bf": _numeric(stat.get("battersFaced")),
                        "outs": _parse_outs(stat.get("inningsPitched", "")),
                    }
                )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame = frame.dropna(subset=["date"]).sort_values("date").drop_duplicates(["pitcher_id", "date"], keep="last")
    return frame.reset_index(drop=True)


def _mean_baseline(history: pd.DataFrame, col: str, tail: int | None = None) -> float:
    values = pd.to_numeric(history.get(col), errors="coerce").dropna()
    if tail is not None:
        values = values.tail(int(tail))
    return float(values.mean()) if not values.empty else float("nan")


def replay_pitcher(starts: pd.DataFrame, target_season: int) -> pd.DataFrame:
    if starts is None or starts.empty:
        return pd.DataFrame()
    data = starts.sort_values("date").reset_index(drop=True).copy()
    rows: list[dict[str, object]] = []
    for _, target in data.loc[data["season"].eq(int(target_season))].iterrows():
        target_date = pd.Timestamp(target["date"])
        prior = data.loc[data["date"] < target_date].copy()
        if len(prior) < MIN_PRIOR_STARTS:
            continue
        actuals = {metric: _numeric(target.get(metric)) for metric in ("pitches", "bf", "outs")}
        if not all(np.isfinite(value) for value in actuals.values()):
            continue
        ctx = build_workload_context(prior[["date", "pitches", "bf", "outs"]], target_date)
        current_season_prior = prior.loc[prior["season"].eq(int(target_season))]
        row: dict[str, object] = {
            "pitcher_id": int(target["pitcher_id"]),
            "game_date": target_date.date().isoformat(),
            "prior_starts": int(len(prior)),
            "current_season_prior_starts": int(len(current_season_prior)),
            "days_since_last_start": ctx.days_since_last_start,
            "leash_label": ctx.leash_label,
            "workload_version": WORKLOAD_VERSION,
        }
        for metric, prediction in (
            ("pitches", ctx.expected_pitches),
            ("bf", ctx.expected_bf),
            ("outs", ctx.expected_outs),
        ):
            row[f"actual_{metric}"] = actuals[metric]
            row[f"workload_{metric}"] = float(prediction)
            row[f"rolling5_{metric}"] = _mean_baseline(prior, metric, tail=5)
            # Season-to-date means exactly that. Before a pitcher's first start of
            # the target season it is unavailable rather than borrowing future data.
            row[f"season_to_date_{metric}"] = _mean_baseline(current_season_prior, metric)
        rows.append(row)
    return pd.DataFrame(rows)


def build_backtest(
    projection_log: pd.DataFrame,
    target_season: int,
    prior_season: int | None = None,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    ids = tracked_pitcher_ids(projection_log)
    if not ids:
        return pd.DataFrame()
    previous = int(prior_season if prior_season is not None else target_season - 1)
    client = session or requests.Session()
    pieces: list[pd.DataFrame] = []
    for pitcher_id in ids:
        try:
            starts = fetch_pitcher_starts(pitcher_id, (previous, int(target_season)), client)
        except requests.RequestException:
            continue
        replayed = replay_pitcher(starts, int(target_season))
        if not replayed.empty:
            pieces.append(replayed)
    return pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()


@dataclass(frozen=True)
class MetricSummary:
    Metric: str
    Evaluated_Starts: int
    Workload_MAE: float
    Workload_RMSE: float
    Workload_Bias: float
    Rolling5_MAE: float
    Rolling5_RMSE: float
    Rolling5_Bias: float
    SeasonToDate_Starts: int
    SeasonToDate_MAE: float
    Relative_MAE_vs_Rolling5: float
    Relative_MAE_vs_SeasonToDate: float
    Workload_Win_Share_vs_Rolling5: float
    Status: str


def _metric_summary(frame: pd.DataFrame, metric: str) -> MetricSummary | None:
    actual = pd.to_numeric(frame.get(f"actual_{metric}"), errors="coerce")
    workload = pd.to_numeric(frame.get(f"workload_{metric}"), errors="coerce")
    rolling = pd.to_numeric(frame.get(f"rolling5_{metric}"), errors="coerce")
    season = pd.to_numeric(frame.get(f"season_to_date_{metric}"), errors="coerce")
    ready = actual.notna() & workload.notna() & rolling.notna()
    if not ready.any():
        return None
    a = actual[ready].astype(float)
    w = workload[ready].astype(float)
    r = rolling[ready].astype(float)
    w_err = w - a
    r_err = r - a
    w_mae = float(w_err.abs().mean())
    r_mae = float(r_err.abs().mean())
    relative_roll = float((r_mae - w_mae) / r_mae) if r_mae > 0 else float("nan")
    win_share = float((w_err.abs() < r_err.abs()).mean())

    season_ready = ready & season.notna()
    if season_ready.any():
        s_err = season[season_ready].astype(float) - actual[season_ready].astype(float)
        s_mae = float(s_err.abs().mean())
        relative_season = float((s_mae - w_mae) / s_mae) if s_mae > 0 else float("nan")
        season_n = int(season_ready.sum())
    else:
        s_mae = relative_season = float("nan")
        season_n = 0

    n = int(ready.sum())
    if n < MIN_STATUS_STARTS:
        status = "LEARNING"
    elif relative_roll >= 0.03 and win_share >= 0.52:
        status = "HELPING"
    elif relative_roll <= -0.03 and win_share <= 0.48:
        status = "HURTING"
    else:
        status = "MIXED"
    return MetricSummary(
        Metric=metric.upper(),
        Evaluated_Starts=n,
        Workload_MAE=w_mae,
        Workload_RMSE=float(np.sqrt(np.mean(np.square(w_err)))),
        Workload_Bias=float(w_err.mean()),
        Rolling5_MAE=r_mae,
        Rolling5_RMSE=float(np.sqrt(np.mean(np.square(r_err)))),
        Rolling5_Bias=float(r_err.mean()),
        SeasonToDate_Starts=season_n,
        SeasonToDate_MAE=s_mae,
        Relative_MAE_vs_Rolling5=relative_roll,
        Relative_MAE_vs_SeasonToDate=relative_season,
        Workload_Win_Share_vs_Rolling5=win_share,
        Status=status,
    )


def summarize_backtest(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    rows = [_metric_summary(frame, metric) for metric in ("pitches", "bf", "outs")]
    return pd.DataFrame([asdict(row) for row in rows if row is not None])


def segment_summary(frame: pd.DataFrame, min_starts: int = 15) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    work = frame.copy()
    days = pd.to_numeric(work.get("days_since_last_start"), errors="coerce")
    work["rest_segment"] = np.select(
        [days <= 4, days.between(5, 6, inclusive="both"), days >= 7],
        ["SHORT REST", "NORMAL REST", "LONG REST"],
        default="UNKNOWN",
    )
    rows: list[dict[str, object]] = []
    for dimension in ("rest_segment", "leash_label"):
        for bucket, group in work.groupby(dimension, dropna=False):
            for metric in ("pitches", "bf", "outs"):
                summary = _metric_summary(group, metric)
                if summary is None or summary.Evaluated_Starts < int(min_starts):
                    continue
                rows.append(
                    {
                        "Dimension": dimension,
                        "Bucket": str(bucket),
                        "Metric": summary.Metric,
                        "Evaluated Starts": summary.Evaluated_Starts,
                        "Workload MAE": summary.Workload_MAE,
                        "Rolling5 MAE": summary.Rolling5_MAE,
                        "Relative MAE vs Rolling5": summary.Relative_MAE_vs_Rolling5,
                        "Win Share vs Rolling5": summary.Workload_Win_Share_vs_Rolling5,
                    }
                )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Leakage-safe workload-v1 backtest over tracked MLB starters.")
    parser.add_argument("--projection-log", type=Path, default=Path("data/projection_log.csv"))
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/workload_backtest.csv"))
    parser.add_argument("--summary", type=Path, default=Path("data/workload_backtest_summary.csv"))
    parser.add_argument("--segments", type=Path, default=Path("data/workload_backtest_segments.csv"))
    args = parser.parse_args()

    history = pd.read_csv(args.projection_log) if args.projection_log.exists() else pd.DataFrame()
    detail = build_backtest(history, target_season=args.season)
    if detail.empty:
        raise SystemExit("No workload backtest rows were produced")
    summary = summarize_backtest(detail)
    segments = segment_summary(detail)
    for path in (args.output, args.summary, args.segments):
        path.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.output, index=False)
    summary.to_csv(args.summary, index=False)
    segments.to_csv(args.segments, index=False)
    print(summary.to_string(index=False))
    print(f"detail_rows={len(detail)} tracked_pitchers={detail['pitcher_id'].nunique()}")


if __name__ == "__main__":
    main()
