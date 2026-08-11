from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BetLeanDecision:
    side: str
    model_probability: float
    edge: float | None
    reason: str


def projection_side(projection_mean: float, line: float, tolerance: float = 1e-9) -> str:
    """Return the only side allowed to be presented as a lean from the point projection."""
    mean = float(projection_mean)
    threshold = float(line)
    if mean > threshold + tolerance:
        return "OVER"
    if mean < threshold - tolerance:
        return "UNDER"
    return "PASS"


def aligned_bet_lean(
    projection_mean: float,
    line: float,
    over_probability: float,
    *,
    over_implied: float | None = None,
    under_implied: float | None = None,
    has_market: bool = False,
    minimum_edge: float = 0.0,
) -> BetLeanDecision:
    """Choose a lean only when model direction, probability, and market edge agree.

    A sportsbook price can make a low-probability outcome look like positive expected value,
    but the app's visible BET LEAN is intentionally stricter: it may never recommend a side
    that conflicts with the point projection. When a live market exists, the aligned side
    must also have positive edge; otherwise the decision is PASS.
    """
    over_probability = min(max(float(over_probability), 0.0), 1.0)
    direction = projection_side(projection_mean, line)
    if direction == "PASS":
        return BetLeanDecision("PASS", 0.5, None, "projection_on_line")

    directional_probability = over_probability if direction == "OVER" else 1.0 - over_probability
    if directional_probability < 0.5:
        return BetLeanDecision("PASS", directional_probability, None, "probability_conflicts_with_projection")

    implied = over_implied if direction == "OVER" else under_implied
    if not has_market or implied is None:
        return BetLeanDecision(direction, directional_probability, None, "model_direction")

    edge = directional_probability - float(implied)
    if edge <= float(minimum_edge):
        return BetLeanDecision("PASS", directional_probability, edge, "no_positive_aligned_edge")

    return BetLeanDecision(direction, directional_probability, edge, "aligned_positive_edge")
