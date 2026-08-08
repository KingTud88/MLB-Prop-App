from __future__ import annotations

import math
import random
from typing import Any


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else default
    except (TypeError, ValueError):
        return default


def mathematical_projection(features: dict[str, Any]) -> float:
    """Conservative pregame K expectation from model features only."""
    recent = _f(features.get("recent5_k_avg"))
    season = _f(features.get("prior_k_per_9")) / 9.0 * max(_f(features.get("expected_batters_faced"), 27.0) / 3.0, 1.0)
    matchup = _f(features.get("opponent_k_rate")) * max(_f(features.get("expected_batters_faced"), 27.0), 1.0)
    hand = _f(features.get("opponent_k_rate_same_hand")) * max(_f(features.get("same_hand_batters")), 0.0)
    components = [x for x in (recent, season, matchup, hand) if x > 0]
    return sum(components) / len(components) if components else 0.0


def simulate_strikeouts(mean_ks: float, simulations: int = 10000, seed: int | None = 42) -> list[float]:
    """Poisson-style K simulation with deterministic seed for reproducible backtests."""
    if mean_ks <= 0 or simulations <= 0:
        return []
    rng = random.Random(seed)
    # Knuth Poisson sampler; sufficient for discrete K-count simulation.
    samples: list[float] = []
    limit = math.exp(-mean_ks)
    for _ in range(simulations):
        k = 0
        product = 1.0
        while product > limit:
            k += 1
            product *= rng.random()
        samples.append(float(k - 1))
    return samples


def simulation_distribution(samples: list[float], line: float | None = None) -> dict[str, float]:
    if not samples:
        return {"sim_mean_ks": 0.0, "sim_median_ks": 0.0, "sim_std_ks": 0.0, "over_probability": 0.0, "under_probability": 0.0}
    ordered = sorted(samples)
    n = len(ordered)
    mean = sum(ordered) / n
    median = ordered[n // 2]
    variance = sum((x - mean) ** 2 for x in ordered) / n
    over = sum(x > line for x in ordered) / n if line is not None else 0.0
    under = sum(x < line for x in ordered) / n if line is not None else 0.0
    return {
        "sim_mean_ks": mean,
        "sim_median_ks": median,
        "sim_std_ks": math.sqrt(variance),
        "over_probability": over,
        "under_probability": under,
    }


def blended_projection(features: dict[str, Any], simulations: int = 10000, simulation_weight: float = 0.5, seed: int | None = 42) -> dict[str, float]:
    math_projection = mathematical_projection(features)
    samples = simulate_strikeouts(math_projection, simulations=simulations, seed=seed)
    dist = simulation_distribution(samples)
    weight = min(max(float(simulation_weight), 0.0), 1.0)
    blended = (1.0 - weight) * math_projection + weight * dist["sim_mean_ks"]
    return {"math_projection": math_projection, "simulation_projection": dist["sim_mean_ks"], "blended_projection": blended, "simulation_std": dist["sim_std_ks"]}
