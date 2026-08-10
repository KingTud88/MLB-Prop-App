from pathlib import Path


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
    assert '"paths_independent": True' in engine
    assert '"market_used_for_forecast": False' in engine


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
