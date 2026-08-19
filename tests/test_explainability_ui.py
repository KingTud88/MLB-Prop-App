from pathlib import Path

from engine.explainability_ui import (
    EXPLAINABILITY_UI_VERSION,
    recommendation_explanation,
    static_explanation,
    top_play_explanation,
)

ROOT = Path(__file__).resolve().parents[1]


def test_shared_explainability_is_attached_to_every_page():
    files = [
        "streamlit_app.py",
        "pages/2_Bet_Tracker.py",
        "pages/4_Projection_History.py",
        "pages/5_Daily_Projection_Run.py",
        "pages/6_Top_Plays.py",
    ]
    for filename in files:
        source = (ROOT / filename).read_text(encoding="utf-8")
        assert "apply_explainability_theme()" in source
        assert "explain_popover(" in source
    assert EXPLAINABILITY_UI_VERSION == "explainability-popovers-v1"


def test_projection_summary_has_metric_decision_and_weather_explainers():
    source = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    assert source.count("projection_metric_explanation(") >= 3
    assert source.count("recommendation_explanation(") >= 3
    assert "weather_explanation(" in source
    assert "static_explanation(\"opposing_batters\")" in source
    assert "static_explanation(\"active_lines\")" in source


def test_secondary_pages_cover_dynamic_decision_blocks():
    tracker = (ROOT / "pages/2_Bet_Tracker.py").read_text(encoding="utf-8")
    daily = (ROOT / "pages/5_Daily_Projection_Run.py").read_text(encoding="utf-8")
    history = (ROOT / "pages/4_Projection_History.py").read_text(encoding="utf-8")
    top = (ROOT / "pages/6_Top_Plays.py").read_text(encoding="utf-8")
    assert "ticket_explanation(ticket)" in tracker
    assert "leg_explanation(leg)" in tracker
    assert "📡 Automated sportsbook lines" in daily
    assert "static_explanation(\"daily_table\")" in daily
    assert "static_explanation(\"odds_credits\")" not in daily
    assert "SportsGameOdds captures real pregame lines automatically" in (ROOT / "engine/explainability_ui.py").read_text(encoding="utf-8")
    assert "static_explanation(\"history_archive\")" in history
    assert "top_play_explanation(play_row)" in top
    assert "static_explanation(\"top_parlay\")" in top


def test_no_line_explanation_refuses_synthetic_decision():
    explanation = recommendation_explanation(
        {"side": "NO LINE", "line": None, "projection_mean": 4.8, "reason": "no_active_market_line"},
        "Strikeouts",
    )
    assert "refuses to manufacture" in explanation.decision
    assert any("4.80" in item for item in explanation.current)


def test_top_play_explanation_uses_existing_action_gate():
    explanation = top_play_explanation({
        "Rank": 1,
        "Pitcher": "Example",
        "Market": "Strikeouts",
        "Side": "OVER",
        "Line": 4.5,
        "Projection": 5.2,
        "Model Probability": 0.61,
        "Data Quality": 79,
        "Line Source": "MANUAL",
        "Decision Evidence": "SUPPORTED",
    })
    assert "at least 55%" in explanation.decision
    assert "at least 60/100" in explanation.decision
    assert static_explanation("ml_shadow").note
