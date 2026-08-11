from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import betabinom


@dataclass(frozen=True)
class OutsProjection:
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
    recent_mean_outs: float
    recent_sd_outs: float
    starts_used: int


def _weighted(series: pd.Series, half_life: float, fallback: float) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna().to_numpy(float)
    if not len(values):
        return float(fallback)
    ages = np.arange(len(values) - 1, -1, -1)
    weights = 0.5 ** (ages / half_life)
    return float(np.average(values, weights=weights))


def _beta_binomial_params(mean_outs: float, variance_outs: float, n: int = 27) -> tuple[float, float]:
    p = float(np.clip(mean_outs / n, 1e-4, 1.0 - 1e-4))
    binom_var = n * p * (1.0 - p)
    target_var = max(float(variance_outs), binom_var + 1e-4)
    ratio = target_var / max(binom_var, 1e-6)
    # Var beta-binomial = n*p*(1-p)*(n+s)/(1+s), s=alpha+beta.
    # Clamp to a stable over-dispersed range; ratio cannot exceed n.
    ratio = float(np.clip(ratio, 1.0001, n - 1e-3))
    concentration = (n - ratio) / max(ratio - 1.0, 1e-6)
    concentration = float(np.clip(concentration, 1.0, 5000.0))
    return p * concentration, (1.0 - p) * concentration


def project_total_outs(
    log: pd.DataFrame,
    *,
    seed: int | None = None,
    draws: int = 25_000,
    lines: tuple[float, ...] = (13.5, 14.5, 15.5, 16.5, 17.5, 18.5),
    simulation_weight: float = 0.5,
) -> OutsProjection:
    """Project pitcher total outs with independent simulation and mathematical paths.

    Simulation path: recency-weighted empirical workload bootstrap plus game-level
    noise, bounded to 0-27 outs. Mathematical path: beta-binomial distribution on
    27 possible outs, fit to recent workload mean/variance. Sportsbook prices are
    intentionally not model inputs.
    """
    if log.empty or "outs" not in log:
        raise ValueError("total-outs projection requires game-log 'outs' column")

    starts = log.tail(35).copy()
    outs = pd.to_numeric(starts["outs"], errors="coerce").dropna().clip(0, 27)
    if outs.empty:
        raise ValueError("no usable total-outs history")

    recent_mean = _weighted(outs, 5.0, 16.0)
    recent_sd = float(np.clip(outs.std(ddof=1) if len(outs) > 2 else 4.0, 2.0, 6.5))

    # Simulation path: recency-weighted bootstrap of real starts with modest game noise.
    values = outs.to_numpy(float)
    ages = np.arange(len(values) - 1, -1, -1)
    weights = 0.5 ** (ages / 5.0)
    weights = weights / weights.sum()
    rng = np.random.default_rng(seed)
    base = rng.choice(values, size=int(draws), replace=True, p=weights)
    noise_sd = float(np.clip(recent_sd * 0.35, 0.75, 2.0))
    simulation_samples = np.clip(np.rint(base + rng.normal(0.0, noise_sd, int(draws))), 0, 27).astype(int)
    simulation_mean = float(np.mean(simulation_samples))
    simulation_sd = float(np.std(simulation_samples, ddof=1))

    # Mathematical path: bounded beta-binomial fit to workload distribution.
    mathematical_mean = float(np.clip(recent_mean, 0.0, 27.0))
    historical_var = float(max(outs.var(ddof=1) if len(outs) > 2 else recent_sd**2, 1.0))
    alpha, beta = _beta_binomial_params(mathematical_mean, historical_var, n=27)
    distribution = betabinom(27, alpha, beta)
    mathematical_var = float(distribution.var())
    mathematical_sd = float(math.sqrt(max(mathematical_var, 0.0)))

    sim_probs: dict[float, float] = {}
    math_probs: dict[float, float] = {}
    ensemble_probs: dict[float, float] = {}
    w = float(np.clip(simulation_weight, 0.0, 1.0))
    for line in lines:
        line = float(line)
        cutoff = int(math.floor(line) + 1)
        sim_p = float(np.mean(simulation_samples >= cutoff))
        math_p = float(distribution.sf(cutoff - 1))
        sim_probs[line] = sim_p
        math_probs[line] = math_p
        ensemble_probs[line] = w * sim_p + (1.0 - w) * math_p

    ensemble_mean = w * simulation_mean + (1.0 - w) * mathematical_mean
    ensemble_var = w * (simulation_sd**2 + simulation_mean**2) + (1.0 - w) * (
        mathematical_sd**2 + mathematical_mean**2
    ) - ensemble_mean**2

    return OutsProjection(
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
        recent_mean_outs=recent_mean,
        recent_sd_outs=recent_sd,
        starts_used=int(len(outs)),
    )
