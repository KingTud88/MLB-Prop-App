from __future__ import annotations

import pandas as pd

from engine.outs_projection import project_total_outs


def _log() -> pd.DataFrame:
    return pd.DataFrame({"outs": [15, 18, 16, 17, 14, 19, 18, 16, 20, 15, 17, 18, 16, 19]})


def test_outs_paths_are_independent_and_monotone() -> None:
    result = project_total_outs(_log(), seed=7, draws=20_000, lines=(13.5, 14.5, 15.5, 16.5, 17.5, 18.5))
    assert 0 < result.simulation_mean <= 27
    assert 0 < result.mathematical_mean <= 27
    assert result.simulation_probabilities != result.mathematical_probabilities
    for probs in (result.simulation_probabilities, result.mathematical_probabilities, result.over_probabilities):
        values = [probs[line] for line in (13.5, 14.5, 15.5, 16.5, 17.5, 18.5)]
        assert all(0.0 <= value <= 1.0 for value in values)
        assert values == sorted(values, reverse=True)


def test_outs_half_line_semantics() -> None:
    result = project_total_outs(_log(), seed=11, draws=15_000, lines=(14.5, 15.5))
    sim = result.simulation_samples
    assert result.simulation_probabilities[14.5] == float((sim >= 15).mean())
    assert result.simulation_probabilities[15.5] == float((sim >= 16).mean())


def test_outs_projection_responds_to_workload() -> None:
    low = pd.DataFrame({"outs": [12, 13, 14, 12, 15, 13, 14, 12, 13, 14]})
    high = pd.DataFrame({"outs": [17, 18, 19, 18, 20, 17, 19, 18, 20, 19]})
    low_p = project_total_outs(low, seed=3, draws=10_000)
    high_p = project_total_outs(high, seed=3, draws=10_000)
    assert high_p.ensemble_mean > low_p.ensemble_mean
    assert high_p.over_probabilities[15.5] > low_p.over_probabilities[15.5]
