from pathlib import Path


def test_shared_theme_keeps_cleveland_night_design_tokens():
    source = Path("engine/ui_theme.py").read_text(encoding="utf-8")
    assert 'APP_UI_VERSION = "ui-cleveland-future-v4"' in source
    assert "--sk-red: #e31937" in source
    assert "--sk-bg: #050d1a" in source
    assert "[data-testid=\"stMetric\"]" in source
    assert ".stTabs [aria-selected=\"true\"]" in source
    assert "@media (max-width: 900px)" in source
    assert ".king-title" in source
    assert ".pitcher-card" in source
    assert ".metric-card" in source
    assert ".reco-card" in source
    assert ".section-head" in source
    assert "[data-testid=\"stForm\"]" in source
    assert "[data-testid=\"stProgress\"]" in source
    assert "stExpanderDetails" in source


def test_sidebar_matches_main_projection_navigation_language():
    source = Path("navigation.py").read_text(encoding="utf-8")
    assert "PROJECTION_PARITY_SIDEBAR_V3" in source
    assert "render_sidebar_brand()" in source
    assert 'render_sidebar(active: str = "projection")' in source
    assert "st.radio(" in source
    assert 'label:nth-child(8)::before' in source
    for label in (
        "Projection", "Distribution", "Form & Workload", "Model Card",
        "Bet Tracker", "Projection History", "Daily Projection Run", "Top Plays",
    ):
        assert label in source
    rendered = source[source.index("# PROJECTION_PARITY_SIDEBAR_V3"):]
    assert "st.page_link" not in rendered
    assert "sk-nav-compact-crown" not in rendered
    assert "👑" not in rendered


def test_streamlit_base_theme_matches_shared_skin():
    config = Path(".streamlit/config.toml").read_text(encoding="utf-8")
    assert 'primaryColor = "#E31937"' in config
    assert 'backgroundColor = "#050D1A"' in config
    assert 'showSidebarNavigation = false' in config
