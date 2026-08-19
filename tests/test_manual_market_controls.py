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


def test_daily_run_retires_manual_entry_ui_but_preserves_legacy_line_compatibility():
    projection = Path("streamlit_app.py").read_text(encoding="utf-8")
    daily = Path("pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")

    # Historical MANUAL rows remain readable through the durable overlay even
    # though current-page variables now use accurate active-line names.
    storage = Path("training/projection_storage.py").read_text(encoding="utf-8")
    assert "active_k_line" in projection
    assert "active_outs_line" in projection
    assert "active_hits_line" in projection
    assert "overlay_manual_market_lines" in daily
    assert "commit_projection_archive" not in daily
    assert 'result.at[idx, source_col] = "MANUAL"' in storage
    assert "manual_strikeout_line" in storage
    assert "manual_outs_line" in storage
    assert "manual_hits_allowed_line" in storage

    assert "📡 Automated sportsbook lines" in daily
    assert "daily_manual_k_" not in daily
    assert "daily_manual_outs_" not in daily
    assert "daily_manual_hits_" not in daily
    assert "daily_apply_archive" not in daily


def test_manual_lines_do_not_enter_projection_feature_builder():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    feature_block = source[source.index('def build_engine_features'):source.index('def calculate_projection')]
    assert 'manual_' not in feature_block
    assert 'odds' not in feature_block.lower()
