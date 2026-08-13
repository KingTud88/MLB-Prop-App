from engine.alt_k import ALT_K_MIN_PROBABILITY, best_alt_k


def test_best_alt_k_picks_highest_milestone_above_floor() -> None:
    choice = best_alt_k([(3, 0.92), (4, 0.81), (5, 0.69), (6, 0.42)])
    assert choice is not None
    assert choice.milestone == 4
    assert choice.probability == 0.81


def test_best_alt_k_uses_predeclared_seventy_percent_floor() -> None:
    choice = best_alt_k([(3, ALT_K_MIN_PROBABILITY), (4, ALT_K_MIN_PROBABILITY - 0.001)])
    assert choice is not None
    assert choice.milestone == 3


def test_best_alt_k_returns_none_when_nothing_is_strong_enough() -> None:
    assert best_alt_k([(3, 0.61), (4, 0.48), (5, 0.31)]) is None


def test_best_alt_k_ignores_out_of_range_and_invalid_probabilities() -> None:
    choice = best_alt_k([(2, 0.99), (3, 1.2), (4, 0.75), (11, 0.91)])
    assert choice is not None
    assert choice.milestone == 4
    assert choice.probability == 0.75
