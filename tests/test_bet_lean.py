from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from engine.bet_lean import aligned_bet_lean, projection_side
from engine.projection_engine import ProjectionEngine


def test_projection_side_matches_point_projection() -> None:
    assert projection_side(5.12, 5.5) == "UNDER"
    assert projection_side(5.88, 5.5) == "OVER"
    assert projection_side(5.5, 5.5) == "PASS"


def test_positive_price_edge_cannot_override_projection_direction() -> None:
    # Exact failure mode seen in the UI: projection below 5.5, yet the OVER price
    # looked cheap enough to have positive edge. The visible lean must not say OVER.
    decision = aligned_bet_lean(
        5.12,
        5.5,
        0.405,
        over_implied=0.370,
        under_implied=0.630,
        has_market=True,
    )
    assert decision.side == "PASS"
    assert decision.reason == "no_positive_aligned_edge"


def test_aligned_side_requires_positive_edge() -> None:
    under = aligned_bet_lean(
        5.12,
        5.5,
        0.405,
        over_implied=0.440,
        under_implied=0.550,
        has_market=True,
    )
    assert under.side == "UNDER"
    assert under.edge is not None and under.edge > 0

    no_bet = aligned_bet_lean(
        18.18,
        17.5,
        0.602,
        over_implied=0.608,
        under_implied=0.430,
        has_market=True,
    )
    assert no_bet.side == "PASS"
    assert no_bet.reason == "no_positive_aligned_edge"


def test_half_line_uses_same_calibration_weight_as_winning_integer_milestone(monkeypatch) -> None:
    fake = {
        5: SimpleNamespace(weight_simulation=0.10),
        6: SimpleNamespace(weight_simulation=0.90),
    }
    monkeypatch.setattr(ProjectionEngine, "_historical_calibration", staticmethod(lambda lines: fake))

    features = {
        "pitcher_k_pct": 0.22,
        "opponent_k_pct": 0.22,
        "expected_bf": 23.0,
        "bf_sd": 3.0,
        "historical_k_sd": 2.0,
        "historical_games": 20,
    }
    result = ProjectionEngine(seed=7).project(features, draws=5000, lines=(5.0, 6.0))

    # Over 5.5 is exactly the 6+ event, so both must use the 6+ calibration weight.
    assert result.simulation_probabilities[5.5] == result.simulation_probabilities[6.0]
    assert result.mathematical_probabilities[5.5] == result.mathematical_probabilities[6.0]
    assert result.over_probabilities[5.5] == result.over_probabilities[6.0]
