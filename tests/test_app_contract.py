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


def test_automated_odds_workflow_is_background_owned_and_projection_reuses_snapshot():
    source = APP.read_text(encoding="utf-8")
    daily = (ROOT / "pages" / "5_Daily_Projection_Run.py").read_text(encoding="utf-8")
    capture = (ROOT / ".github" / "workflows" / "sportsgameodds-capture.yml").read_text(encoding="utf-8")
    provider = (ROOT / "engine" / "sportsgameodds.py").read_text(encoding="utf-8")
    assert "get_event_props" not in source
    assert "extract_player_odds" not in source
    assert "load_pitcher_market_odds" in source
    assert "refresh_strikeout_snapshot" not in daily
    assert "resolve_api_key" not in daily
    assert "SPORTSGAMEODDS_API_KEY" in capture
    assert "pitcher_strikeouts" in provider and "pitcher_outs" in provider and "pitcher_hits_allowed" in provider
    assert "pitcher_strikeouts_alternate" in source


def test_navigation_does_not_expose_separate_odds_page():
    source = NAV.read_text(encoding="utf-8")
    assert '"pages/3_Odds_API.py"' not in source
    assert '"Projection"' in source


def test_calibration_stays_50_50_until_minimum_sample():
    frame = pd.DataFrame({
        "game_date": ["2026-08-10"] * 10,
        "captured_at_utc": ["2026-08-10T14:00:00Z"] * 10,
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
        "game_date": ["2026-08-10"] * 40,
        "captured_at_utc": ["2026-08-10T14:00:00Z"] * 40,
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
            "game_date": "2026-08-10",
            "captured_at_utc": "2026-08-10T14:00:00Z",
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


def test_schedule_api_error_stops_before_empty_slate_warning():
    source = APP.read_text(encoding="utf-8")
    expected = (
                  'schedule,err=get_schedule(selected_date.isoformat())\n'
                  'if err:\n'
                  '    st.error(err)\n'
                  '    st.stop()\n'
                  'if not schedule:\n'
                  '    st.warning("No announced probable pitchers are available for this date.")\n'
                  '    st.stop()'
              )
    assert expected in source
