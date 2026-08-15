from pathlib import Path


def test_command_center_v6_exposes_reusable_hero_and_matchup_components():
    source = Path("engine/ui_command_center.py").read_text(encoding="utf-8")
    assert 'COMMAND_CENTER_UI_VERSION = "cle-command-center-v6"' in source
    assert "def render_command_center_hero(" in source
    assert "def render_matchup_strip(" in source
    assert "cc-hero-fallback" in source
    assert "st.image(str(MASCOT_PATH)" not in source
    assert "key=\"cc_hero_shell\"" in source
    assert "cc-hero-status" in source
    assert "cc-quality-track" in source
    assert "cc-matchup-strip" in source
    assert "cc-team-mark" in source
    assert "@media (max-width:620px)" in source
    assert "data:image/png;base64" not in source
    assert "raw.githubusercontent.com" not in source


def test_main_projection_uses_v6_components_without_removing_model_flow():
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


def test_main_projection_lower_command_center_is_presentation_only():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    theme = Path("engine/ui_command_center.py").read_text(encoding="utf-8")
    assert 'key="cc_bet_action_panel"' in source
    assert 'key="cc_market_command_row"' in source
    assert 'key="cc_parlay_panel"' in source
    assert "BET TRACKER / PARLAY ACTIONS" in source
    assert "PROJECTION PARLAY BUILDER" in source
    assert ".st-key-cc_bet_action_panel" in theme
    assert ".st-key-cc_market_command_row" in theme
    assert ".st-key-cc_parlay_panel" in theme
    assert "render_add_bet_button(add1,k_reco" in source
    assert "render_add_bet_button(add2,out_reco" in source
    assert "render_add_bet_button(add3,hit_reco" in source
    assert "build_market_table(proj,odds_rows,hits_proj)" in source
    assert "render_projection_parlay_builder()" in source
    assert "this page never calls the Odds API" in source
