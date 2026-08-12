from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd

WORKLOAD_VERSION = "workload-v1"


@dataclass(frozen=True)
class WorkloadContext:
    version: str
    starts_used: int
    expected_pitches: float
    expected_bf: float
    expected_outs: float
    bf_sd: float
    outs_sd: float
    pitch_sd: float
    recent_pitches: float
    recent_bf: float
    recent_outs: float
    pitches_per_bf: float
    outs_per_bf: float
    days_since_last_start: int | None
    rest_multiplier: float
    pitch_trend: float
    bf_trend: float
    outs_trend: float
    leash_index: float
    leash_label: str

    def snapshot_fields(self) -> dict[str, object]:
        return {
            "workload_version": self.version,
            "workload_starts_used": self.starts_used,
            "expected_pitches": self.expected_pitches,
            "expected_bf": self.expected_bf,
            "expected_outs": self.expected_outs,
            "workload_bf_sd": self.bf_sd,
            "workload_outs_sd": self.outs_sd,
            "workload_pitch_sd": self.pitch_sd,
            "recent_pitches": self.recent_pitches,
            "recent_bf": self.recent_bf,
            "recent_outs": self.recent_outs,
            "pitches_per_bf": self.pitches_per_bf,
            "outs_per_bf": self.outs_per_bf,
            "days_since_last_start": self.days_since_last_start,
            "workload_rest_multiplier": self.rest_multiplier,
            "pitch_trend": self.pitch_trend,
            "bf_trend": self.bf_trend,
            "outs_trend": self.outs_trend,
            "leash_index": self.leash_index,
            "leash_label": self.leash_label,
        }


def _number(value: object, default: float) -> float:
    try:
        parsed = float(value)
        return parsed if np.isfinite(parsed) else float(default)
    except (TypeError, ValueError):
        return float(default)


def _weighted(series: pd.Series, half_life: float, fallback: float) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna().to_numpy(float)
    if not len(values):
        return float(fallback)
    ages = np.arange(len(values) - 1, -1, -1)
    weights = 0.5 ** (ages / float(half_life))
    return float(np.average(values, weights=weights))


def _trend(series: pd.Series, recent_games: int = 3, prior_games: int = 3) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna().to_numpy(float)
    needed = int(recent_games) + int(prior_games)
    if len(values) < needed:
        return 0.0
    recent = float(np.mean(values[-int(recent_games):]))
    prior = float(np.mean(values[-needed:-int(recent_games)]))
    if prior <= 0:
        return 0.0
    return float(np.clip(recent / prior - 1.0, -0.30, 0.30))


def _prepare_starts(log: pd.DataFrame, game_date: object | None) -> pd.DataFrame:
    if log.empty:
        return pd.DataFrame(columns=["date", "pitches", "bf", "outs"])
    starts = log.copy()
    for col in ("pitches", "bf", "outs"):
        if col not in starts.columns:
            starts[col] = np.nan
        starts[col] = pd.to_numeric(starts[col], errors="coerce")
    if "date" not in starts.columns:
        starts["date"] = pd.NaT
    starts["date"] = pd.to_datetime(starts["date"], errors="coerce")

    # Strictly pregame when a target date is known. This makes the helper safe
    # for historical reconstruction and prevents a later start from leaking in.
    target = pd.to_datetime(game_date, errors="coerce") if game_date is not None else pd.NaT
    if pd.notna(target):
        target_day = pd.Timestamp(target).normalize()
        dated = starts["date"].notna()
        starts = starts.loc[~dated | (starts["date"].dt.normalize() < target_day)].copy()

    starts = starts.loc[starts[["pitches", "bf", "outs"]].notna().any(axis=1)].copy()
    if starts.empty:
        return starts
    if starts["date"].notna().any():
        starts = starts.sort_values("date", na_position="first")
    return starts.tail(35).reset_index(drop=True)


def _rest_multiplier(days_since_last_start: int | None) -> float:
    # Only short-rest situations receive a conservative workload penalty.
    # Typical or long rest is neutral because long rest can mean many things.
    if days_since_last_start is None:
        return 1.0
    if days_since_last_start <= 4:
        return 0.96
    if days_since_last_start == 5:
        return 0.985
    return 1.0


def build_workload_context(log: pd.DataFrame, game_date: object | None = None) -> WorkloadContext:
    """Estimate pregame starter exposure from real starter workload history.

    The model combines recency-weighted pitches, batters faced, outs, pitch
    efficiency, workload trend, and conservative short-rest handling. It uses
    baseball history only; sportsbook data is never an input.
    """
    starts = _prepare_starts(log, game_date)
    if starts.empty:
        return WorkloadContext(
            version=WORKLOAD_VERSION,
            starts_used=0,
            expected_pitches=88.0,
            expected_bf=22.0,
            expected_outs=16.0,
            bf_sd=3.5,
            outs_sd=4.0,
            pitch_sd=12.0,
            recent_pitches=88.0,
            recent_bf=22.0,
            recent_outs=16.0,
            pitches_per_bf=4.0,
            outs_per_bf=16.0 / 22.0,
            days_since_last_start=None,
            rest_multiplier=1.0,
            pitch_trend=0.0,
            bf_trend=0.0,
            outs_trend=0.0,
            leash_index=88.0 / 90.0,
            leash_label="NORMAL",
        )

    recent_pitches = _weighted(starts["pitches"], 4.0, 88.0)
    long_pitches = _weighted(starts["pitches"], 12.0, recent_pitches)
    recent_bf = _weighted(starts["bf"], 5.0, 22.0)
    long_bf = _weighted(starts["bf"], 12.0, recent_bf)
    recent_outs = _weighted(starts["outs"], 5.0, 16.0)
    long_outs = _weighted(starts["outs"], 12.0, recent_outs)

    pitch_trend = _trend(starts["pitches"])
    bf_trend = _trend(starts["bf"])
    outs_trend = _trend(starts["outs"])

    days_since_last_start: int | None = None
    target = pd.to_datetime(game_date, errors="coerce") if game_date is not None else pd.NaT
    dated = starts["date"].dropna()
    if pd.notna(target) and not dated.empty:
        delta = pd.Timestamp(target).normalize() - pd.Timestamp(dated.iloc[-1]).normalize()
        days_since_last_start = max(int(delta.days), 0)
    rest_multiplier = _rest_multiplier(days_since_last_start)

    pitch_base = 0.70 * recent_pitches + 0.30 * long_pitches
    trend_multiplier = 1.0 + float(np.clip(pitch_trend * 0.20, -0.05, 0.05))
    expected_pitches = float(np.clip(pitch_base * trend_multiplier * rest_multiplier, 60.0, 112.0))

    ratios = starts.loc[(starts["bf"] > 0) & (starts["pitches"] > 0), "pitches"] / starts.loc[(starts["bf"] > 0) & (starts["pitches"] > 0), "bf"]
    fallback_ppbf = recent_pitches / max(recent_bf, 1.0)
    pitches_per_bf = float(np.clip(_weighted(ratios, 6.0, fallback_ppbf), 2.8, 5.5))
    bf_from_pitches = expected_pitches / max(pitches_per_bf, 1e-6)
    bf_baseline = 0.70 * recent_bf + 0.30 * long_bf
    expected_bf = float(np.clip(0.55 * bf_baseline + 0.45 * bf_from_pitches, 10.0, 35.0))

    out_ratios = starts.loc[(starts["bf"] > 0) & starts["outs"].notna(), "outs"] / starts.loc[(starts["bf"] > 0) & starts["outs"].notna(), "bf"]
    fallback_opbf = recent_outs / max(recent_bf, 1.0)
    outs_per_bf = float(np.clip(_weighted(out_ratios, 6.0, fallback_opbf), 0.45, 0.90))
    outs_from_bf = expected_bf * outs_per_bf
    outs_baseline = 0.70 * recent_outs + 0.30 * long_outs
    expected_outs = float(np.clip(0.60 * outs_baseline + 0.40 * outs_from_bf, 6.0, 24.0))

    bf_values = pd.to_numeric(starts["bf"], errors="coerce").dropna()
    outs_values = pd.to_numeric(starts["outs"], errors="coerce").dropna()
    pitch_values = pd.to_numeric(starts["pitches"], errors="coerce").dropna()
    bf_sd = float(np.clip(bf_values.std(ddof=1) if len(bf_values) > 2 else 3.5, 1.5, 6.5))
    outs_sd = float(np.clip(outs_values.std(ddof=1) if len(outs_values) > 2 else 4.0, 2.0, 6.5))
    pitch_sd = float(np.clip(pitch_values.std(ddof=1) if len(pitch_values) > 2 else 12.0, 6.0, 25.0))

    leash_index = float(np.clip(expected_pitches / 90.0, 0.65, 1.25))
    if leash_index < 0.92:
        leash_label = "TIGHT"
    elif leash_index > 1.08:
        leash_label = "LONG"
    else:
        leash_label = "NORMAL"

    return WorkloadContext(
        version=WORKLOAD_VERSION,
        starts_used=int(len(starts)),
        expected_pitches=expected_pitches,
        expected_bf=expected_bf,
        expected_outs=expected_outs,
        bf_sd=bf_sd,
        outs_sd=outs_sd,
        pitch_sd=pitch_sd,
        recent_pitches=float(recent_pitches),
        recent_bf=float(recent_bf),
        recent_outs=float(recent_outs),
        pitches_per_bf=pitches_per_bf,
        outs_per_bf=outs_per_bf,
        days_since_last_start=days_since_last_start,
        rest_multiplier=float(rest_multiplier),
        pitch_trend=float(pitch_trend),
        bf_trend=float(bf_trend),
        outs_trend=float(outs_trend),
        leash_index=leash_index,
        leash_label=leash_label,
    )


def workload_snapshot_fields(context: WorkloadContext | Mapping[str, object]) -> dict[str, object]:
    if isinstance(context, WorkloadContext):
        return context.snapshot_fields()
    return dict(context)
