import numpy as np

from engine.projection_engine import ProjectionEngine


def test_half_line_cutoff_matches_baseball_prop_rule():
    assert ProjectionEngine._line_cutoff(3.5) == 4
    assert ProjectionEngine._line_cutoff(4.5) == 5
    assert ProjectionEngine._line_cutoff(5.5) == 6


def test_half_line_probability_is_not_lower_integer_milestone():
    engine = ProjectionEngine(simulation_weight=0.5, seed=7)
    samples = np.array([3, 4, 5, 6, 7, 8], dtype=np.int16)
    assert np.mean(samples >= ProjectionEngine._line_cutoff(5.5)) == 0.5
    assert np.mean(samples >= 5) == 4 / 6


def test_projection_result_keeps_sim_math_and_ensemble_probabilities_separate(monkeypatch):
    """Regression guard: public SIM/MATH fields must never expose the blend."""
    monkeypatch.setattr(
        ProjectionEngine,
        "_historical_calibration",
        staticmethod(lambda lines: {int(np.floor(line)): None for line in lines}),
    )

    engine = ProjectionEngine(simulation_weight=0.37, seed=19)
    features = {
        "pitcher_k_pct": 0.31,
        "opponent_k_pct": 0.27,
        "handedness_factor": 1.04,
        "arsenal_factor": 1.03,
        "park_factor": 1.01,
        "umpire_factor": 1.0,
        "weather_factor": 1.0,
        "expected_bf": 24.5,
        "bf_sd": 3.2,
        "rest_factor": 1.0,
        "historical_k_sd": 2.35,
        "historical_games": 20,
    }

    result = engine.project(features, draws=6000, lines=(3.0, 4.0, 5.0, 6.0, 7.0, 8.0))
    raw_sim = result.metadata["raw_simulation_probabilities"]
    raw_math = result.metadata["raw_mathematical_probabilities"]
    calibrated = result.metadata["calibrated_market_probabilities"]

    assert result.simulation_probabilities == raw_sim
    assert result.mathematical_probabilities == raw_math
    assert result.over_probabilities == calibrated

    # The two analytical paths should remain independently observable, and the
    # final ensemble should be their requested weighted blend at every test line.
    assert any(abs(raw_sim[line] - raw_math[line]) > 1e-6 for line in (3.0, 4.0, 5.0, 6.0, 7.0, 8.0))
    for line in (3.0, 4.0, 5.0, 6.0, 7.0, 8.0):
        expected = 0.37 * raw_sim[line] + 0.63 * raw_math[line]
        assert np.isclose(result.over_probabilities[line], expected)
