from pathlib import Path


def test_main_projection_reads_current_sportsgameodds_snapshot_for_all_markets():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "from engine.sportsgameodds import load_pitcher_market_odds" in source
    assert "odds_rows=load_pitcher_market_odds(game.pitcher_name,selected_date.isoformat())" in source
    assert "load_pitcher_strikeout_odds" not in source
    assert 'market_recommendation(proj,odds_rows,"pitcher_strikeouts_alternate"' in source
    assert 'market_recommendation(proj,odds_rows,"pitcher_outs_alternate"' in source
    assert 'r.get("market") in {"pitcher_hits_allowed","pitcher_hits_allowed_alternate"}' in source


def test_main_projection_keeps_durable_legacy_archive_overlay_and_no_line_guard():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "overlay_manual_market_lines" in source
    assert "active_strikeout_line" in source
    assert "active_outs_line" in source
    assert "active_hits_allowed_line" in source
    assert "NO ACTIVE LINE" in source
