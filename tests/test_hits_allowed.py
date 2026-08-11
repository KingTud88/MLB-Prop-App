from __future__ import annotations

import pandas as pd

from engine.hits_allowed import project_hits_allowed


def _log() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "bf": [22, 24, 21, 25, 23, 20, 26, 24, 22, 25, 23, 24],
            "hits": [5, 6, 4, 7, 5, 4, 8, 6, 5, 7, 5, 6],
        }
    )


def test_hits_allowed_paths_are_independent_and_monotone() -> None:
    result = project_hits_allowed(
        _log(), expected_bf=23.5, opponent_hit_rate=0.245, seed=7, draws=20_000,
        lines=(3.5, 4.5, 5.5, 6.5, 7.5),
    )

    assert result.simulation_mean > 0
    assert result.mathematical_mean > 0
    assert result.ensemble_mean > 0
    assert result.simulation_probabilities != result.mathematical_probabilities

    for probs in (
        result.simulation_probabilities,
        result.mathematical_probabilities,
        result.over_probabilities,
    ):
        values = [probs[line] for line in (3.5, 4.5, 5.5, 6.5, 7.5)]
        assert all(0.0 <= value <= 1.0 for value in values)
        assert values == sorted(values, reverse=True)


def test_hits_allowed_half_line_semantics() -> None:
    result = project_hits_allowed(_log(), seed=11, draws=15_000, lines=(4.5, 5.5))
    sim = result.simulation_samples

    assert result.simulation_probabilities[4.5] == float((sim >= 5).mean())
    assert result.simulation_probabilities[5.5] == float((sim >= 6).mean())


def test_opponent_contact_changes_projection_direction() -> None:
    low_contact = project_hits_allowed(_log(), opponent_hit_rate=0.205, seed=3, draws=10_000)
    high_contact = project_hits_allowed(_log(), opponent_hit_rate=0.285, seed=3, draws=10_000)

    assert high_contact.ensemble_mean > low_contact.ensemble_mean
    assert high_contact.over_probabilities[5.5] > low_contact.over_probabilities[5.5]
