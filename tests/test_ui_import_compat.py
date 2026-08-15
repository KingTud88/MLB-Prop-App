from pathlib import Path


def test_new_sidebar_helpers_are_deploy_skew_safe():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "try:" in source
    assert "from engine.ui_command_center import render_sidebar_brand, render_sidebar_pitcher_identity" in source
    assert "except ImportError:" in source
    assert "def render_sidebar_brand()" in source
    assert "def render_sidebar_pitcher_identity(" in source
    assert "apply_command_center_theme" in source
    assert "render_command_center_hero" in source
    assert "render_matchup_strip" in source
