from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np


@dataclass(frozen=True)
class PregameFeatures:
    """Normalized pregame feature contract for the projection engine."""

    pitcher_k_pct: float
    opponent_k_pct: float
    handedness_factor: float = 1.0
    arsenal_factor: float = 1.0
    park_factor: float = 1.0
    umpire_factor: float = 1.0
    weather_factor: float = 1.0
    expected_bf: float = 23.0
    bf_sd: float = 3.5
    rest_factor: float = 1.0
    historical_k_sd: float = 2.0
    historical_games: int = 0
    lineup_batters: int = 0
    arsenal_sample_size: int = 0
    weather_available: bool = False
    umpire_available: bool = False

    def as_dict(self) -> dict[str, float | int]:
        return {
            "pitcher_k_pct": self.pitcher_k_pct,
            "opponent_k_pct": self.opponent_k_pct,
            "handedness_factor": self.handedness_factor,
            "arsenal_factor": self.arsenal_factor,
            "park_factor": self.park_factor,
            "umpire_factor": self.umpire_factor,
            "weather_factor": self.weather_factor,
            "expected_bf": self.expected_bf,
            "bf_sd": self.bf_sd,
            "rest_factor": self.rest_factor,
            "historical_k_sd": self.historical_k_sd,
            "historical_games": self.historical_games,
            "lineup_batters": self.lineup_batters,
            "arsenal_sample_size": self.arsenal_sample_size,
            "weather_available": int(self.weather_available),
            "umpire_available": int(self.umpire_available),
        }


def _number(value: object, default: float) -> float:
    try:
        value = float(value)
        return value if np.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def handedness_factor(pitcher_hand: str | None, lineup: list[Mapping[str, object]] | None) -> float:
    """Estimate the lineup-level handedness effect from batter splits.

    If batter-level split data is supplied, it is preferred over a generic
    platoon assumption. The result is deliberately bounded so handedness
    cannot overwhelm skill, workload, or matchup information.
    """
    if not lineup or pitcher_hand not in {"L", "R"}:
        return 1.0

    values: list[float] = []
    for batter in lineup:
        same = pitcher_hand == str(batter.get("bats", "")).upper()
        split_k = batter.get("k_pct_vs_lhp" if pitcher_hand == "L" else "k_pct_vs_rhp")
        overall_k = batter.get("k_pct")
        split = _number(split_k, _number(overall_k, 0.224))
        baseline = _number(overall_k, 0.224)
        if baseline > 0:
            values.append(np.clip(split / baseline, 0.80, 1.20))
        elif same:
            values.append(1.0)

    return float(np.clip(np.mean(values) if values else 1.0, 0.85, 1.15))


def lineup_k_rate(lineup: list[Mapping[str, object]] | None, pitcher_hand: str | None) -> float:
    """Return projected opponent K rate using pitcher-specific batter splits."""
    if not lineup:
        return 0.224

    key = "k_pct_vs_lhp" if pitcher_hand == "L" else "k_pct_vs_rhp"
    values = []
    weights = []
    for batter in lineup:
        value = _number(batter.get(key), _number(batter.get("k_pct"), 0.224))
        pa = max(_number(batter.get("expected_pa"), 4.0), 1.0)
        values.append(np.clip(value, 0.03, 0.55))
        weights.append(pa)
    return float(np.average(values, weights=weights))


def build_pregame_features(
    pitcher: Mapping[str, object],
    lineup: list[Mapping[str, object]] | None = None,
    context: Mapping[str, object] | None = None,
) -> PregameFeatures:
    """Convert raw pitcher/lineup/context records into the engine contract."""
    context = context or {}
    hand = str(pitcher.get("hand", pitcher.get("throws", "R"))).upper()
    opponent_k = lineup_k_rate(lineup, hand)

    arsenal = _number(context.get("arsenal_factor"), 1.0)
    park = _number(context.get("park_factor"), 1.0)
    umpire = _number(context.get("umpire_factor"), 1.0)
    weather = _number(context.get("weather_factor"), 1.0)
    expected_bf = _number(context.get("expected_bf"), _number(pitcher.get("expected_bf"), 23.0))

    return PregameFeatures(
        pitcher_k_pct=np.clip(_number(pitcher.get("k_pct"), _number(pitcher.get("K%"), 0.224)), 0.05, 0.45),
        opponent_k_pct=opponent_k,
        handedness_factor=handedness_factor(hand, lineup),
        arsenal_factor=np.clip(arsenal, 0.85, 1.15),
        park_factor=np.clip(park, 0.90, 1.10),
        umpire_factor=np.clip(umpire, 0.92, 1.08),
        weather_factor=np.clip(weather, 0.94, 1.06),
        expected_bf=np.clip(expected_bf, 10.0, 35.0),
        bf_sd=np.clip(_number(context.get("bf_sd"), 3.5), 1.0, 7.0),
        rest_factor=np.clip(_number(context.get("rest_factor"), 1.0), 0.95, 1.05),
        historical_k_sd=np.clip(_number(pitcher.get("historical_k_sd"), 2.0), 0.75, 4.5),
        historical_games=int(_number(pitcher.get("historical_games"), 0)),
        lineup_batters=len(lineup or []),
        arsenal_sample_size=int(_number(context.get("arsenal_sample_size"), 0)),
        weather_available=bool(context.get("weather_available", False)),
        umpire_available=bool(context.get("umpire_available", False)),
    )
