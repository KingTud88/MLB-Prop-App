from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Mapping

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ProjectionResult:
    """Auditable output from the independent simulation/math paths and ensemble."""

    simulation_mean: float
    simulation_sd: float
    mathematical_mean: float
    mathematical_sd: float
    ensemble_mean: float
    ensemble_sd: float
    over_probabilities: dict[float, float]
    simulation_probabilities: dict[float, float]
    mathematical_probabilities: dict[float, float]
    simulation_samples: np.ndarray
    mathematical_pmf: np.ndarray
    confidence: float
    data_quality: float
    drivers: tuple[tuple[str, float, str], ...] = field(default_factory=tuple)
    metadata: Mapping[str, object] = field(default_factory=dict)


class ProjectionEngine:
    """Two-path strikeout projection engine.

    Path 1: complete-game Monte Carlo simulation, sampling workload and then
    every plate appearance independently.

    Path 2: a transparent mathematical probability model using the same
    pregame features but a separate Negative-Binomial distribution. It does
    not reuse the simulation samples.

    The market line is never an input to either baseball forecast path.
    """

    def __init__(self, simulation_weight: float = 0.50, seed: int | None = None) -> None:
        self.simulation_weight = float(np.clip(simulation_weight, 0.0, 1.0))
        self.seed = seed

    @staticmethod
    def _clip(value: float, low: float, high: float) -> float:
        return float(np.clip(value, low, high))

    @staticmethod
    def _safe_float(value: object, default: float = 0.0) -> float:
        try:
            result = float(value)
            return result if np.isfinite(result) else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _nb_pmf(mean: float, sd: float, max_k: int = 20) -> np.ndarray:
        mean = max(float(mean), 0.05)
        variance = max(float(sd) ** 2, mean + 0.01)
        # NB variance = mean + mean^2 / r. Large r approaches Poisson.
        r = max(mean * mean / max(variance - mean, 1e-6), 0.25)
        p = r / (r + mean)
        values = []
        for k in range(max_k + 1):
            log_p = (
                math.lgamma(k + r)
                - math.lgamma(r)
                - math.lgamma(k + 1)
                + r * math.log(p)
                + k * math.log(max(1.0 - p, 1e-12))
            )
            values.append(math.exp(log_p))
        probs = np.asarray(values, dtype=float)
        tail = max(0.0, 1.0 - probs.sum())
        probs[-1] += tail
        return probs / probs.sum()

    def mathematical_projection(self, features: Mapping[str, float]) -> tuple[float, float, dict[str, float]]:
        """Independent mathematical baseline from pregame rates and context."""
        pitcher_k = self._clip(self._safe_float(features.get("pitcher_k_pct"), 0.224), 0.05, 0.45)
        batter_k = self._clip(self._safe_float(features.get("opponent_k_pct"), 0.224), 0.05, 0.45)
        handedness = self._clip(self._safe_float(features.get("handedness_factor"), 1.0), 0.85, 1.15)
        arsenal = self._clip(self._safe_float(features.get("arsenal_factor"), 1.0), 0.85, 1.15)
        park = self._clip(self._safe_float(features.get("park_factor"), 1.0), 0.90, 1.10)
        umpire = self._clip(self._safe_float(features.get("umpire_factor"), 1.0), 0.92, 1.08)
        weather = self._clip(self._safe_float(features.get("weather_factor"), 1.0), 0.94, 1.06)
        workload = self._clip(self._safe_float(features.get("expected_bf"), 23.0) / 23.0, 0.70, 1.30)
        rest = self._clip(self._safe_float(features.get("rest_factor"), 1.0), 0.95, 1.05)

        matchup_k_rate = math.sqrt(pitcher_k * batter_k)
        mean = 23.0 * matchup_k_rate * handedness * arsenal * park * umpire * weather * workload * rest
        mean = self._clip(mean, 0.25, 14.0)
        historical_sd = self._safe_float(features.get("historical_k_sd"), math.sqrt(max(mean * 1.15, 1.0)))
        sd = self._clip(historical_sd, 0.75, 4.5)
        factors = {
            "Pitcher K skill": pitcher_k / 0.224 - 1.0,
            "Opponent K matchup": batter_k / 0.224 - 1.0,
            "Handedness": handedness - 1.0,
            "Arsenal matchup": arsenal - 1.0,
            "Expected workload": workload - 1.0,
            "Park": park - 1.0,
            "Umpire": umpire - 1.0,
            "Weather": weather - 1.0,
            "Rest": rest - 1.0,
        }
        return mean, sd, factors

    def simulate_game(self, features: Mapping[str, float], draws: int = 25000) -> tuple[np.ndarray, float]:
        """Simulate complete games through plate appearances, not from a fitted PMF."""
        draws = max(1000, int(draws))
        rng = np.random.default_rng(self.seed)

        expected_bf = self._clip(self._safe_float(features.get("expected_bf"), 23.0), 10.0, 35.0)
        pitcher_k = self._clip(self._safe_float(features.get("pitcher_k_pct"), 0.224), 0.05, 0.45)
        batter_k = self._clip(self._safe_float(features.get("opponent_k_pct"), 0.224), 0.05, 0.45)
        handedness = self._clip(self._safe_float(features.get("handedness_factor"), 1.0), 0.85, 1.15)
        arsenal = self._clip(self._safe_float(features.get("arsenal_factor"), 1.0), 0.85, 1.15)
        park = self._clip(self._safe_float(features.get("park_factor"), 1.0), 0.90, 1.10)
        umpire = self._clip(self._safe_float(features.get("umpire_factor"), 1.0), 0.92, 1.08)
        weather = self._clip(self._safe_float(features.get("weather_factor"), 1.0), 0.94, 1.06)

        p_k = math.sqrt(pitcher_k * batter_k) * handedness * arsenal * park * umpire * weather
        p_k = self._clip(p_k, 0.015, 0.55)
        bf_sd = self._clip(self._safe_float(features.get("bf_sd"), 3.5), 1.0, 7.0)
        bf = np.rint(rng.normal(expected_bf, bf_sd, draws)).astype(int)
        bf = np.clip(bf, 10, 38)

        outcomes = np.zeros(draws, dtype=np.int16)
        for pa in range(38):
            active = bf > pa
            if not np.any(active):
                break
            # A small latent game effect creates realistic game-to-game variance
            # while retaining PA-level independence inside each simulated game.
            latent = np.exp(rng.normal(0.0, 0.10, int(active.sum())))
            probs = np.clip(p_k * latent, 0.002, 0.70)
            outcomes[active] += rng.random(int(active.sum())) < probs

        return outcomes, float(outcomes.mean())

    def project(
        self,
        features: Mapping[str, float],
        draws: int = 25000,
        lines: tuple[float, ...] = tuple(float(x) for x in range(3, 11)),
    ) -> ProjectionResult:
        sim_samples, sim_mean = self.simulate_game(features, draws=draws)
        sim_sd = float(sim_samples.std(ddof=1))
        math_mean, math_sd, factors = self.mathematical_projection(features)
        math_pmf = self._nb_pmf(math_mean, math_sd)

        w = self.simulation_weight
        ensemble_mean = w * sim_mean + (1.0 - w) * math_mean
        ensemble_sd = math.sqrt(max(w * sim_sd**2 + (1.0 - w) * math_sd**2, 0.01))

        sim_probs: dict[float, float] = {}
        math_probs: dict[float, float] = {}
        ensemble_probs: dict[float, float] = {}
        for line in lines:
            cutoff = int(math.floor(float(line)) + 1)
            sim_p = float(np.mean(sim_samples >= cutoff))
            math_p = float(math_pmf[cutoff:].sum()) if cutoff < len(math_pmf) else 0.0
            sim_probs[float(line)] = sim_p
            math_probs[float(line)] = math_p
            ensemble_probs[float(line)] = float(w * sim_p + (1.0 - w) * math_p)

        quality_inputs = [
            self._safe_float(features.get("historical_games"), 0),
            self._safe_float(features.get("lineup_batters"), 0),
            self._safe_float(features.get("arsenal_sample_size"), 0),
            self._safe_float(features.get("weather_available"), 0),
            self._safe_float(features.get("umpire_available"), 0),
        ]
        quality = self._clip(
            35.0
            + min(35.0, quality_inputs[0] * 1.5)
            + min(15.0, quality_inputs[1])
            + min(10.0, quality_inputs[2] / 50.0)
            + 5.0 * quality_inputs[3]
            + 5.0 * quality_inputs[4],
            0.0,
            100.0,
        )
        confidence = self._clip(0.45 + 0.005 * quality - min(abs(sim_mean - math_mean) / 12.0, 0.20), 0.35, 0.95)
        driver_rows = tuple(
            (name, float(value), "positive" if value > 0 else "negative" if value < 0 else "neutral")
            for name, value in sorted(factors.items(), key=lambda item: abs(item[1]), reverse=True)
        )
        return ProjectionResult(
            simulation_mean=float(sim_mean),
            simulation_sd=sim_sd,
            mathematical_mean=float(math_mean),
            mathematical_sd=float(math_sd),
            ensemble_mean=float(ensemble_mean),
            ensemble_sd=float(ensemble_sd),
            over_probabilities=ensemble_probs,
            simulation_probabilities=sim_probs,
            mathematical_probabilities=math_probs,
            simulation_samples=sim_samples,
            mathematical_pmf=math_pmf,
            confidence=float(confidence),
            data_quality=float(quality),
            drivers=driver_rows,
            metadata={
                "engine_version": "1.1.0",
                "simulation_draws": draws,
                "simulation_weight": w,
                "paths_independent": True,
                "market_used_for_forecast": False,
            },
        )
