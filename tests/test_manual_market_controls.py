from pathlib import Path


def test_projection_lean_cards_support_manual_line_and_odds_without_forecast_feedback():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert 'MANUAL LINE / ODDS' in source
    assert 'Use manual market' in source
    assert 'American odds' in source
    assert 'Sportsbook implied' in source
    assert 'Manual market is execution-only' in source
    assert 'manual_market_recommendation' in source
    assert 'market_model_probability' in source


def test_all_three_projection_markets_have_manual_controls():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert 'key_prefix=f"manual_k:{game.key}"' in source
    assert 'key_prefix=f"manual_outs:{game.key}"' in source
    assert 'key_prefix=f"manual_hits:{game.key}"' in source
    assert 'market_key="pitcher_strikeouts"' in source
    assert 'market_key="pitcher_outs"' in source
    assert 'market_key="pitcher_hits_allowed"' in source


def test_manual_controls_do_not_enter_projection_feature_builder():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    feature_block = source[source.index('def build_engine_features'):source.index('def calculate_projection')]
    assert 'manual_' not in feature_block
    assert 'odds' not in feature_block.lower()
