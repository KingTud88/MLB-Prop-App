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
