from pathlib import Path


def test_shared_theme_keeps_cleveland_night_design_tokens():
    source = Path("engine/ui_theme.py").read_text(encoding="utf-8")
    assert 'APP_UI_VERSION = "ui-cleveland-future-v2"' in source
    assert "--sk-red: #e31937" in source
    assert "--sk-bg: #050d1a" in source
    assert "[data-testid=\"stMetric\"]" in source
    assert ".stTabs [aria-selected=\"true\"]" in source
    assert "@media (max-width: 900px)" in source


def test_sidebar_has_custom_navigation_and_logo_fallback():
    source = Path("navigation.py").read_text(encoding="utf-8")
    assert "CLEVELAND NIGHT MODE" in source
    assert "sk-logo-fallback" in source
    assert 'render_sidebar(active: str = "projection")' in source
    for label in ("Projection", "Top Plays", "Bet Tracker", "Projection History", "Daily Projection Run"):
        assert label in source


def test_streamlit_base_theme_matches_shared_skin():
    config = Path(".streamlit/config.toml").read_text(encoding="utf-8")
    assert 'primaryColor = "#E31937"' in config
    assert 'backgroundColor = "#050D1A"' in config
    assert 'showSidebarNavigation = false' in config
