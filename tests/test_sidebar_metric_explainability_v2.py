from pathlib import Path

from engine.explainability_ui import METRIC_HELP_VERSION, metric_help

ROOT = Path(__file__).resolve().parents[1]


def test_secondary_sidebar_uses_compact_projection_language():
    source = (ROOT / "navigation.py").read_text(encoding="utf-8")
    assert "SECONDARY_COMPACT_SIDEBAR_V2" in source
    assert "sk-nav-compact-crown" in source
    assert "sk-nav-compact-script" in source
    assert "sk-nav-compact-king" in source
    rendered = source[source.index("with st.sidebar:"):]
    assert "sk-nav-mascot" not in rendered
    assert "CLE-themed MLB starter projection engine" in rendered


def test_metric_help_is_formula_level_and_read_only():
    assert METRIC_HELP_VERSION == "metric-help-v2"
    for key in (
        "history_k_hit_rate", "history_k_mae", "history_outs_mae",
        "tracker_roi", "daily_confirmed", "top_actionable",
    ):
        text = metric_help(key)
        assert "What it is:" in text
        assert ("Formula:" in text) or ("How it is calculated:" in text)
        assert "How to read it:" in text


def test_history_scoreboard_has_help_on_every_marked_metric():
    source = (ROOT / "pages/4_Projection_History.py").read_text(encoding="utf-8")
    keys = (
        "history_evidence_rows", "history_resolved_games", "history_k_range_hits",
        "history_k_hit_rate", "history_hits_range_hits", "history_hits_hit_rate",
        "history_outs_range_hits", "history_outs_hit_rate", "history_k_mae",
        "history_hits_mae", "history_outs_mae",
    )
    for key in keys:
        assert f'metric_help("{key}")' in source
    assert "eligible intervals" in source
    assert "valid projection/result pairs" in source


def test_secondary_summary_scorecards_use_metric_help():
    expected = {
        "pages/2_Bet_Tracker.py": ("tracker_bets", "tracker_record", "tracker_pending", "tracker_net", "tracker_roi"),
        "pages/5_Daily_Projection_Run.py": ("daily_projected", "daily_new", "daily_refreshed", "daily_history_only", "daily_errors", "daily_confirmed"),
        "pages/6_Top_Plays.py": ("top_highest_probability", "top_actionable", "top_decision_supported", "top_signal_supported", "top_live_prices"),
    }
    for path, keys in expected.items():
        source = (ROOT / path).read_text(encoding="utf-8")
        for key in keys:
            assert f'metric_help("{key}")' in source
