from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from engine.model_card_ui import build_path_table, build_probability_table


def test_path_table_preserves_three_existing_model_paths():
    table = build_path_table(
        simulation_mean=5.8,
        simulation_sd=1.7,
        mathematical_mean=6.2,
        mathematical_sd=1.9,
        ensemble_mean=6.0,
        ensemble_sd=1.8,
        mean_label="Mean K",
    )

    assert table["Path"].tolist() == ["Simulation", "Mathematical", "Ensemble"]
    assert table["Mean K"].tolist() == [5.8, 6.2, 6.0]
    assert table["SD"].tolist() == [1.7, 1.9, 1.8]


def test_probability_table_uses_existing_calibration_weights_without_prices():
    def calibrator(_history: pd.DataFrame, line: float) -> SimpleNamespace:
        return SimpleNamespace(weight_simulation=0.60 if line == 4.5 else 0.40)

    table = build_probability_table(
        simulation_probabilities={4.5: 0.70, 5.5: 0.50},
        mathematical_probabilities={4.5: 0.50, 5.5: 0.30},
        history=pd.DataFrame(),
        calibrator=calibrator,
    )

    assert table["Line"].tolist() == [4.5, 5.5]
    assert table["Probability"].round(6).tolist() == [0.62, 0.38]
    assert table["Sim Weight"].tolist() == [0.60, 0.40]


def test_model_card_helper_is_three_market_presentation_only():
    source = Path("engine/model_card_ui.py").read_text(encoding="utf-8")
    assert 'st.tabs(["Strikeouts", "Hits Allowed", "Outs"])' in source
    assert "hits_calibration_report(history)" in source
    assert "outs_calibration_report(history)" in source
    assert "load_pitcher_market_odds" not in source
    assert "implied_prob" not in source
    assert "aligned_bet_lean" not in source
    assert "project_hits_allowed" not in source
    assert "project_total_outs" not in source
