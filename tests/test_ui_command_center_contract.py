from pathlib import Path


def test_command_center_v2_exposes_reusable_hero_and_matchup_components():
    source = Path("engine/ui_command_center.py").read_text(encoding="utf-8")
    assert 'COMMAND_CENTER_UI_VERSION = "cle-command-center-v2"' in source
    assert "def render_command_center_hero(" in source
    assert "def render_matchup_strip(" in source
    assert "cc-hero-mascot" in source
    assert "cc-hero-status" in source
    assert "cc-quality-track" in source
    assert "cc-matchup-strip" in source
    assert "cc-team-mark" in source
    assert "@media (max-width:620px)" in source


def test_main_projection_uses_v2_components_without_removing_model_flow():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "render_command_center_hero(" in source
    assert "render_matchup_strip(" in source
    assert "confidence=proj.confidence" in source
    assert "quality=proj.quality" in source
    assert "weather_icon=weather_risk.icon or \"\"" in source
    # Core projection and market-separation contracts remain in the page.
    assert "calculate_projection(" in source
    assert "load_pitcher_strikeout_odds" in source
    assert "this page never calls the Odds API" in source
