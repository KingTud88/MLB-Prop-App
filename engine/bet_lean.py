from __future__ import annotations

from dataclasses import dataclass


# A visible green/red BET LEAN should mean more than "slightly above 50%."
# This is a presentation/decision guardrail only; it does not alter any baseball
# projection or probability. Keep the threshold fixed across K/outs/hits.
DEFAULT_MINIMUM_PROBABILITY = 0.58
DEFAULT_MINIMUM_EDGE = 0.02


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
    minimum_probability: float = DEFAULT_MINIMUM_PROBABILITY,
    minimum_edge: float = DEFAULT_MINIMUM_EDGE,
) -> BetLeanDecision:
    """Return OVER/UNDER only when direction, confidence, and market edge agree.

    The point projection determines which side is eligible. The directional
    probability must clear a fixed confidence floor even when no sportsbook is
    loaded. When a market is loaded, that same side must additionally clear the
    minimum model-vs-implied edge. Sportsbook data never creates the forecast.
    """
    over_probability = min(max(float(over_probability), 0.0), 1.0)
    direction = projection_side(projection_mean, line)
    if direction == "PASS":
        return BetLeanDecision("PASS", 0.5, None, "projection_on_line")

    directional_probability = over_probability if direction == "OVER" else 1.0 - over_probability
    if directional_probability < 0.5:
        return BetLeanDecision("PASS", directional_probability, None, "probability_conflicts_with_projection")
    if directional_probability < float(minimum_probability):
        return BetLeanDecision("PASS", directional_probability, None, "insufficient_model_confidence")

    implied = over_implied if direction == "OVER" else under_implied
    if not has_market or implied is None:
        return BetLeanDecision(direction, directional_probability, None, "model_confidence")

    edge = directional_probability - float(implied)
    if edge < float(minimum_edge):
        return BetLeanDecision("PASS", directional_probability, edge, "insufficient_aligned_edge")

    return BetLeanDecision(direction, directional_probability, edge, "aligned_actionable_edge")
