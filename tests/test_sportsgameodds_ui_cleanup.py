from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_daily_run_has_no_obsolete_manual_or_paid_line_controls():
    text = _text("pages/5_Daily_Projection_Run.py")
    for token in (
        "Backup Paid Data",
        "LOAD STRIKEOUT LINES · BACKUP API",
        "Odds API credits remaining",
        "commit_projection_archive(",
        "apply_active_market_lines(",
        "apply_paid_strikeout_lines(",
        "refresh_strikeout_snapshot",
    ):
        assert token not in text
    assert "Automated sportsbook lines" in text


def test_top_plays_uses_saved_sportsgameodds_prices_without_direct_odds_api_runtime():
    text = _text("pages/6_Top_Plays.py")
    for token in (
        "api.the-odds-api.com",
        "odds_events(",
        "event_props(",
        "load_top_plays_live_prices",
        "Odds API usage from the last manual Top 5 load",
        "Paid Odds API",
        "Credit Saver",
    ):
        assert token not in text
    assert "load_pitcher_market_odds" in text
    assert "attach_sportsgameodds_prices" in text
    assert "SportsGameOdds is primary" in text


def test_main_projection_copy_and_source_labels_match_automated_feed():
    text = _text("streamlit_app.py")
    assert "Use the paid manual button" not in text
    assert "PAID API · SAVED SNAPSHOT" not in text
    assert "Automated real sportsbook lines show their provider/book source" in text
    assert "SPORTSGAMEODDS" in text


def test_projection_history_counts_real_lines_and_preserves_legacy_manual_context():
    text = _text("pages/4_Projection_History.py")
    assert "Real lines attached" in text
    assert "Manual lines attached" not in text
    assert " real lines · " in text
    assert "legacy MANUAL lines remain orange" in text
    assert "active_strikeout_line_source" in text


def test_explainability_matches_automated_sportsbook_workflow():
    text = _text("engine/explainability_ui.py")
    assert '"history_real_lines"' in text
    assert '"history_manual_lines"' not in text
    assert '"manual_lines": Explanation(' not in text
    assert '"odds_credits": Explanation(' not in text
    assert "SportsGameOdds captures real pregame lines automatically" in text
