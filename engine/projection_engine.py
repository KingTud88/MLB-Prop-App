from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Mapping

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ProjectionResult:
    """Auditable output from both projection paths and their ensemble."""

    simulation_mean: float
    simulation_sd: float
    mathematical_mean: float
    mathematical_sd: float
    ensemble_mean: float
    ensemble_sd: float
    over_probabilities: dict[float, float]
    confidence: float
    data_quality: float
    drivers: tuple[tuple[str, float, str], ...] = field(default_factory=tuple)
    metadata: Mapping[str, object] = field(default_factory=dict)


class ProjectionEngine:
    """Two-path strikeout projection engine.

    Path 1 is a plate-appearance Monte Carlo simulator.
    Path 2 is a mathematical baseline that can be replaced by a trained,
    walk-forward gradient-boosted model without changing the UI contract.

    All feature inputs are explicitly pregame inputs. The engine never uses
    the market line to produce the baseball forecast.
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

    def mathematical_projection(self, features: Mapping[str, float]) -> tuple[float, float, dict[str, float]]:
        """Transparent mathematical projection used until the trained GBM is available."""
        pitcher_k = self._clip(self._safe_float(features.get("pitcher_k_pct"), 0.224), 0.05, 0.45)
        batter_k = self._clip(self._safe_float(features.get("opponent_k_pct"), 0.224), 0.05, 0.45)
        handedness = self._clip(self._safe_float(features.get("handedness_factor"), 1.0), 0.85, 1.15)
        arsenal = self._clip(self._safe_float(features.get("arsenal_factor"), 1.0), 0.85, 1.15)
        park = self._clip(self._safe_float(features.get("park_factor"), 1.0), 0.90, 1.10)
        umpire = self._clip(self._safe_float(features.get("umpire_factor"), 1.0), 0.92, 1.08)
        weather = self._clip(self._safe_float(features.get("weather_factor"), 1.0), 0.94, 1.06)
        workload = self._clip(self._safe_float(features.get("expected_bf"), 23.0) / 23.0, 0.70, 1.30)
        rest = self._clip(self._safe_float(features.get("rest_factor"), 1.0), 0.95, 1.05)

        # Geometric blend avoids letting one rate dominate the other.
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

        # Game-to-game workload uncertainty is sampled first, then each game is
        # simulated PA-by-PA. This creates a genuinely independent simulation path.
        bf_sd = self._clip(self._safe_float(features.get("bf_sd"), 3.5), 1.0, 7.0)
        bf = np.rint(rng.normal(expected_bf, bf_sd, draws)).astype(int)
        bf = np.clip(bf, 10, 38)

        outcomes = np.zeros(draws, dtype=np.int16)
        # Chunking avoids a huge draws x plate appearances allocation.
        for pa in range(38):
            active = bf > pa
            if not np.any(active):
                break
            # Mild latent game variance makes each simulated game distinct.
            latent = np.exp(rng.normal(0.0, 0.10, int(active.sum())))
            probs = np.clip(p_k * latent, 0.002, 0.70)
            outcomes[active] += rng.random(int(active.sum())) < probs

        return outcomes, float(outcomes.mean())

    def project(self, features: Mapping[str, float], draws: int = 25000, lines: tuple[float, ...] = (4.5, 5.5, 6.5)) -> ProjectionResult:
        sim_samples, sim_mean = self.simulate_game(features, draws=draws)
        sim_sd = float(sim_samples.std(ddof=1))
        math_mean, math_sd, factors = self.mathematical_projection(features)

        # Until the walk-forward GBM is trained, the mathematical path is the
        # production baseline. The contract remains stable when GBM replaces it.
        w = self.simulation_weight
        ensemble_mean = w * sim_mean + (1.0 - w) * math_mean
        ensemble_sd = math.sqrt(max(w * sim_sd**2 + (1.0 - w) * math_sd**2, 0.01))

        over_probs: dict[float, float] = {}
        for line in lines:
            # Combine the empirical simulation probability with a normal CDF
            # approximation of the mathematical path.
            sim_p = float(np.mean(sim_samples > line))
            z = (line + 0.5 - math_mean) / max(math_sd, 0.25)
            math_p = 0.5 * math.erfc(z / math.sqrt(2.0))
            over_probs[float(line)] = float(w * sim_p + (1.0 - w) * math_p)

        quality_inputs = [
            self._safe_float(features.get("historical_games"), 0),
            self._safe_float(features.get("lineup_batters"), 0),
            self._safe_float(features.get("arsenal_sample_size"), 0),
            self._safe_float(features.get("weather_available"), 0),
            self._safe_float(features.get("umpire_available"), 0),
        ]
        quality = self._clip(35.0 + min(35.0, quality_inputs[0] * 1.5) + min(15.0, quality_inputs[1]) + min(10.0, quality_inputs[2] / 50.0) + 5.0 * quality_inputs[3] + 5.0 * quality_inputs[4], 0.0, 100.0)
        confidence = self._clip(0.45 + 0.005 * quality - min(abs(sim_mean - math_mean) / 12.0, 0.20), 0.35, 0.95)

        driver_rows = tuple((name, float(value), "positive" if value > 0 else "negative" if value < 0 else "neutral") for name, value in sorted(factors.items(), key=lambda item: abs(item[1]), reverse=True))
        return ProjectionResult(
            simulation_mean=float(sim_mean),
            simulation_sd=sim_sd,
            mathematical_mean=float(math_mean),
            mathematical_sd=float(math_sd),
            ensemble_mean=float(ensemble_mean),
            ensemble_sd=float(ensemble_sd),
            over_probabilities=over_probs,
            confidence=float(confidence),
            data_quality=float(quality),
            drivers=driver_rows,
            metadata={"engine_version": "1.0.0", "simulation_draws": draws, "simulation_weight": w, "gbm_status": "not_trained"},
        )
