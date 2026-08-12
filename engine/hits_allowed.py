from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import nbinom

LEAGUE_HIT_PER_BF = 0.235


@dataclass(frozen=True)
class HitsAllowedProjection:
    simulation_mean: float
    simulation_sd: float
    mathematical_mean: float
    mathematical_sd: float
    ensemble_mean: float
    ensemble_sd: float
    simulation_probabilities: dict[float, float]
    mathematical_probabilities: dict[float, float]
    over_probabilities: dict[float, float]
    simulation_samples: np.ndarray
    pitcher_hit_rate: float
    opponent_hit_rate: float
    matchup_hit_rate: float


def _weighted(series: pd.Series, half_life: float, fallback: float) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna().to_numpy(float)
    if not len(values):
        return float(fallback)
    ages = np.arange(len(values) - 1, -1, -1)
    weights = 0.5 ** (ages / half_life)
    return float(np.average(values, weights=weights))


def _shrunk_rate(hits: float, bf: float, prior_rate: float = LEAGUE_HIT_PER_BF, prior_bf: float = 180.0) -> float:
    return float((hits + prior_rate * prior_bf) / max(bf + prior_bf, 1.0))


def _negative_binomial_params(mean: float, variance: float) -> tuple[float, float]:
    mean = max(float(mean), 1e-6)
    variance = max(float(variance), mean + 1e-6)
    size = mean * mean / max(variance - mean, 1e-6)
    prob = size / (size + mean)
    return size, prob


def project_hits_allowed(
    log: pd.DataFrame,
    *,
    expected_bf: float | None = None,
    bf_sd: float | None = None,
    opponent_hit_rate: float | None = None,
    park_factor: float = 1.0,
    seed: int | None = None,
    draws: int = 25_000,
    lines: tuple[float, ...] = (3.5, 4.5, 5.5, 6.5, 7.5),
    simulation_weight: float = 0.5,
) -> HitsAllowedProjection:
    """Project pitcher hits allowed with independent simulation and mathematical paths.

    The simulation path samples workload and a beta-distributed per-batter hit rate,
    then draws hits from a binomial game model. The mathematical path uses an
    over-dispersed Negative Binomial distribution fit from the pitcher's recent
    hits-allowed history. Sportsbook prices are intentionally not inputs.

    ``expected_bf`` and ``bf_sd`` may be supplied by the shared pregame workload
    engine. When omitted, this function retains its historical workload fallback.
    """
    if log.empty or "bf" not in log or "hits" not in log:
        raise ValueError("hits-allowed projection requires game-log 'bf' and 'hits' columns")

    starts = log.tail(35).copy()
    starts["bf"] = pd.to_numeric(starts["bf"], errors="coerce")
    starts["hits"] = pd.to_numeric(starts["hits"], errors="coerce")
    starts = starts.dropna(subset=["bf", "hits"])
    if starts.empty:
        raise ValueError("no usable hits-allowed history")

    total_bf = float(starts["bf"].clip(lower=0).sum())
    total_hits = float(starts["hits"].clip(lower=0).sum())
    pitcher_rate = _shrunk_rate(total_hits, total_bf)

    opponent_rate = float(opponent_hit_rate) if opponent_hit_rate is not None else LEAGUE_HIT_PER_BF
    opponent_rate = float(np.clip(opponent_rate, 0.12, 0.36))
    matchup_rate = float(np.sqrt(max(pitcher_rate, 1e-6) * max(opponent_rate, 1e-6)))
    matchup_rate = float(np.clip(matchup_rate * float(park_factor), 0.10, 0.40))

    if expected_bf is None:
        expected_bf = _weighted(starts["bf"], 5.0, 22.0)
    expected_bf = float(np.clip(expected_bf, 10.0, 35.0))
    if bf_sd is None:
        bf_sd = float(starts["bf"].std(ddof=1) if len(starts) > 2 else 3.5)
    bf_sd = float(np.clip(bf_sd, 1.0, 7.0))

    rng = np.random.default_rng(seed)
    simulated_bf = np.clip(np.rint(rng.normal(expected_bf, bf_sd, int(draws))), 6, 40).astype(int)

    # Keep the simulation path independent from the mathematical distribution:
    # game-to-game hit-rate uncertainty is represented with a beta draw.
    beta_strength = float(np.clip(total_bf * 0.35, 80.0, 450.0))
    alpha = max(matchup_rate * beta_strength, 1e-3)
    beta = max((1.0 - matchup_rate) * beta_strength, 1e-3)
    sampled_rates = rng.beta(alpha, beta, int(draws))
    simulation_samples = rng.binomial(simulated_bf, sampled_rates)
    simulation_mean = float(np.mean(simulation_samples))
    simulation_sd = float(np.std(simulation_samples, ddof=1))

    mathematical_mean = float(matchup_rate * expected_bf)
    historical_var = float(starts["hits"].var(ddof=1)) if len(starts) > 2 else mathematical_mean + 1.5
    workload_var = float((matchup_rate * bf_sd) ** 2)
    mathematical_var = max(historical_var * 0.65 + workload_var, mathematical_mean + 0.25)
    mathematical_sd = float(math.sqrt(mathematical_var))
    nb_size, nb_prob = _negative_binomial_params(mathematical_mean, mathematical_var)

    sim_probs: dict[float, float] = {}
    math_probs: dict[float, float] = {}
    ensemble_probs: dict[float, float] = {}
    w = float(np.clip(simulation_weight, 0.0, 1.0))
    for line in lines:
        line = float(line)
        cutoff = int(math.floor(line) + 1)
        sim_p = float(np.mean(simulation_samples >= cutoff))
        math_p = float(nbinom.sf(cutoff - 1, nb_size, nb_prob))
        sim_probs[line] = sim_p
        math_probs[line] = math_p
        ensemble_probs[line] = w * sim_p + (1.0 - w) * math_p

    ensemble_mean = w * simulation_mean + (1.0 - w) * mathematical_mean
    ensemble_var = w * (simulation_sd**2 + simulation_mean**2) + (1.0 - w) * (
        mathematical_sd**2 + mathematical_mean**2
    ) - ensemble_mean**2

    return HitsAllowedProjection(
        simulation_mean=simulation_mean,
        simulation_sd=simulation_sd,
        mathematical_mean=mathematical_mean,
        mathematical_sd=mathematical_sd,
        ensemble_mean=float(ensemble_mean),
        ensemble_sd=float(math.sqrt(max(ensemble_var, 0.0))),
        simulation_probabilities=sim_probs,
        mathematical_probabilities=math_probs,
        over_probabilities=ensemble_probs,
        simulation_samples=simulation_samples,
        pitcher_hit_rate=pitcher_rate,
        opponent_hit_rate=opponent_rate,
        matchup_hit_rate=matchup_rate,
    )
