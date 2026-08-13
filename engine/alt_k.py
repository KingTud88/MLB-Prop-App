from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


ALT_K_MIN_PROBABILITY = 0.70
ALT_K_MIN_MILESTONE = 3
ALT_K_MAX_MILESTONE = 10


@dataclass(frozen=True)
class AltKChoice:
    milestone: int
    probability: float


def best_alt_k(
    milestone_probabilities: Iterable[tuple[int, float]],
    *,
    minimum_probability: float = ALT_K_MIN_PROBABILITY,
    minimum_milestone: int = ALT_K_MIN_MILESTONE,
    maximum_milestone: int = ALT_K_MAX_MILESTONE,
) -> AltKChoice | None:
    """Return the highest K milestone that still clears the hit-rate floor.

    This is display-only decision support. It does not inspect sportsbook lines,
    prices, or bets and it never changes the underlying projection. Choosing the
    highest qualifying milestone avoids the unhelpful result where the safest
    (lowest) milestone wins simply because it has the largest raw probability.
    """
    floor = float(minimum_probability)
    eligible: list[AltKChoice] = []
    for milestone, probability in milestone_probabilities:
        try:
            k = int(milestone)
            p = float(probability)
        except (TypeError, ValueError):
            continue
        if k < int(minimum_milestone) or k > int(maximum_milestone):
            continue
        if not 0.0 <= p <= 1.0:
            continue
        if p >= floor:
            eligible.append(AltKChoice(k, p))
    if not eligible:
        return None
    return max(eligible, key=lambda choice: (choice.milestone, choice.probability))
