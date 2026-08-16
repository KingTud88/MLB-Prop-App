from pathlib import Path


def test_projection_uses_daily_lines_without_local_manual_market_editor():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "MANUAL LINE / ODDS" not in source
    assert "Use manual market" not in source
    assert "manual_market_recommendation" not in source
    assert "overlay_manual_market_lines" in source
    assert "apply_active_line_to_recommendation" in source
    assert "NO ACTIVE LINE" in source
    assert 'side_text=f"{projection_text} PROJ"' in source


def test_daily_run_is_single_persistent_manual_line_source_for_all_three_markets():
    projection = Path("streamlit_app.py").read_text(encoding="utf-8")
    daily = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")
    assert "manual_k_line" in projection
    assert "manual_outs_line" in projection
    assert "manual_hits_line" in projection
    assert "daily_manual_k_" in daily
    assert "daily_manual_outs_" in daily
    assert "daily_manual_hits_" in daily
    assert "APPLY LINES + ADD TO PROJECTION ARCHIVE" in daily


def test_manual_lines_do_not_enter_projection_feature_builder():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    feature_block = source[source.index('def build_engine_features'):source.index('def calculate_projection')]
    assert 'manual_' not in feature_block
    assert 'odds' not in feature_block.lower()
