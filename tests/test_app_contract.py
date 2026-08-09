from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_app.py"
NAV = ROOT / "navigation.py"


def test_streamlit_source_compiles():
    compile(APP.read_text(encoding="utf-8"), str(APP), "exec")


def test_projection_contains_two_path_engine_contract():
    source = APP.read_text(encoding="utf-8")
    assert "25,000 simulated games" in source
    assert "_sok_simulated_path" in source
    assert "_sok_math_projection" in source
    assert "true 50/50" in source
    assert "TWO_PATH_DETAILS" in source


def test_projection_owns_odds_workflow():
    source = APP.read_text(encoding="utf-8")
    assert "_sok_live_pitcher_odds" in source
    assert "THE_ODDS_API_KEY" in source


def test_navigation_does_not_expose_separate_odds_page():
    source = NAV.read_text(encoding="utf-8")
    assert '"pages/3_Odds_API.py"' not in source
    assert '"Projection"' in source
