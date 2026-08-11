from pathlib import Path

import pandas as pd

from engine.calibration import PROBABILITY_SEMANTICS, calibrate_blend, milestone_calibration_report
from engine.starter_history import HISTORY_SEMANTICS


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_app.py"
NAV = ROOT / "navigation.py"
ENGINE = ROOT / "engine" / "projection_engine.py"


def test_streamlit_source_compiles():
    compile(APP.read_text(encoding="utf-8"), str(APP), "exec")


def test_projection_contains_two_path_engine_contract():
    source = APP.read_text(encoding="utf-8")
    engine = ENGINE.read_text(encoding="utf-8")
    assert "ProjectionEngine" in source
    assert "draws=simulations" in source
    assert "range(3,11)" in source
    assert "simulate_game" in engine
    assert "mathematical_projection" in engine
    assert '"paths_independent":True' in engine.replace(" ", "")
    assert '"market_used_for_forecast":False' in engine.replace(" ", "")


def test_projection_owns_odds_workflow():
    source = APP.read_text(encoding="utf-8")
    assert "get_event_props" in source
    assert "extract_player_odds" in source
    assert "THE_ODDS_API_KEY" in source
    assert "pitcher_strikeouts_alternate" in source


def test_navigation_does_not_expose_separate_odds_page():
    source = NAV.read_text(encoding="utf-8")
    assert '"pages/3_Odds_API.py"' not in source
    assert '"Projection"' in source


def test_calibration_stays_50_50_until_minimum_sample():
    frame = pd.DataFrame({
        "sim_5p": [0.70] * 10,
        "math_5p": [0.55] * 10,
        "actual_strikeouts": [5, 4, 6, 3, 5, 4, 7, 2, 6, 5],
        "probability_semantics": [PROBABILITY_SEMANTICS] * 10,
        "history_semantics": [HISTORY_SEMANTICS] * 10,
    })
    result = calibrate_blend(frame, 5, min_observations=30)
    assert result.observations == 10
    assert result.calibrated is False
    assert result.weight_simulation == 0.50
    assert result.weight_math == 0.50


def test_strikeout_calibration_excludes_mixed_appearance_history():
    frame = pd.DataFrame({
        "sim_5p": [0.70] * 40,
        "math_5p": [0.55] * 40,
        "actual_strikeouts": [5] * 40,
        "probability_semantics": [PROBABILITY_SEMANTICS] * 40,
        "history_semantics": ["legacy-mixed-appearances"] * 40,
    })
    result = calibrate_blend(frame, 5, min_observations=30)
    assert result.observations == 0
    assert result.calibrated is False
    assert result.weight_simulation == 0.50
    assert result.weight_math == 0.50


def test_milestone_report_covers_3_plus_through_10_plus():
    rows = []
    for actual in range(2, 12):
        row = {
            "actual_strikeouts": actual,
            "probability_semantics": PROBABILITY_SEMANTICS,
            "history_semantics": HISTORY_SEMANTICS,
        }
        for line in range(3, 11):
            row[f"sim_{line}p"] = 0.60
            row[f"math_{line}p"] = 0.50
        rows.append(row)
    report = milestone_calibration_report(pd.DataFrame(rows), min_observations=5)
    assert list(report["Line"]) == [f"{line}+" for line in range(3, 11)]
    assert len(report) == 8
    assert set(["Simulation Brier", "Math Brier", "Calibrated Brier", "Simulation Weight", "Math Weight"]).issubset(report.columns)
