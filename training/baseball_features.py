from __future__ import annotations

import math
from typing import Any


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def rate(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def build_baseball_features(
    pitcher_logs: list[dict[str, Any]],
    opponent_batters: list[dict[str, Any]] | None = None,
    pitcher_hand: str | None = None,
    park_factor: float = 1.0,
    wind_mph: float = 0.0,
    wind_out_mph: float = 0.0,
    wind_in_mph: float = 0.0,
    temperature_f: float = 70.0,
    recent_days_rest: float = 5.0,
) -> dict[str, float]:
    """Create leakage-safe, pregame baseball features from already historical inputs.

    This module intentionally accepts data rather than fetching it. The collector is
    responsible for guaranteeing that every input was available before first pitch.
    """
    logs = pitcher_logs or []
    innings = sum(safe_float(x.get("inningsPitched")) for x in logs)
    strikeouts = sum(safe_float(x.get("strikeOuts")) for x in logs)
    batters = sum(safe_float(x.get("battersFaced")) for x in logs)
    walks = sum(safe_float(x.get("baseOnBalls")) for x in logs)
    hits = sum(safe_float(x.get("hits")) for x in logs)
    games = len(logs)

    last3 = logs[:3]
    last5 = logs[:5]
    k3 = sum(safe_float(x.get("strikeOuts")) for x in last3)
    k5 = sum(safe_float(x.get("strikeOuts")) for x in last5)
    ip3 = sum(safe_float(x.get("inningsPitched")) for x in last3)
    ip5 = sum(safe_float(x.get("inningsPitched")) for x in last5)

    batters = opponent_batters or []
    opp_k_rate = sum(safe_float(b.get("strikeout_rate")) for b in batters) / len(batters) if batters else 0.0
    opp_k_rate_same_hand = sum(
        safe_float(b.get("strikeout_rate_same_hand")) for b in batters
    ) / len(batters) if batters else 0.0

    hand_is_left = 1.0 if str(pitcher_hand or "").upper().startswith("L") else 0.0

    return {
        "prior_games": float(games),
        "prior_strikeouts": strikeouts,
        "prior_ip": innings,
        "prior_k_per_9": rate(strikeouts * 9.0, innings),
        "prior_k_rate": rate(strikeouts, batters),
        "prior_bb_rate": rate(walks, batters),
        "prior_hit_rate": rate(hits, batters),
        "recent3_k_per_9": rate(k3 * 9.0, ip3),
        "recent5_k_per_9": rate(k5 * 9.0, ip5),
        "recent3_k_avg": rate(k3, len(last3)),
        "recent5_k_avg": rate(k5, len(last5)),
        "opponent_k_rate": opp_k_rate,
        "opponent_k_rate_same_hand": opp_k_rate_same_hand,
        "pitcher_is_left_handed": hand_is_left,
        "park_factor": safe_float(park_factor, 1.0),
        "wind_mph": safe_float(wind_mph),
        "wind_out_mph": safe_float(wind_out_mph),
        "wind_in_mph": safe_float(wind_in_mph),
        "temperature_f": safe_float(temperature_f, 70.0),
        "days_rest": safe_float(recent_days_rest, 5.0),
        "weather_k_factor": 1.0 + (safe_float(wind_in_mph) * 0.002) - (safe_float(wind_out_mph) * 0.002),
    }


def simulation_summary(simulated_ks: list[float]) -> dict[str, float]:
    """Summarize an independently generated game simulation."""
    if not simulated_ks:
        return {"sim_mean_ks": 0.0, "sim_median_ks": 0.0, "sim_std_ks": 0.0}
    values = sorted(float(x) for x in simulated_ks)
    mean = sum(values) / len(values)
    median = values[len(values) // 2]
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return {"sim_mean_ks": mean, "sim_median_ks": median, "sim_std_ks": math.sqrt(variance)}
