from pathlib import Path

from engine.explainability_ui import METRIC_HELP_VERSION, metric_help

ROOT = Path(__file__).resolve().parents[1]


def test_secondary_sidebar_uses_exact_projection_navigation_language():
    source = (ROOT / "navigation.py").read_text(encoding="utf-8")
    assert "PROJECTION_PARITY_SIDEBAR_V3" in source
    assert "render_sidebar_brand()" in source
    assert 'st.radio(' in source
    assert '"Projection", "Distribution", "Form & Workload", "Model Card"' in source
    assert '"Bet Tracker", "Projection History", "Daily Projection Run", "Top Plays"' in source
    assert 'label:nth-child(8)::before' in source
    rendered = source[source.index("# PROJECTION_PARITY_SIDEBAR_V3"):]
    assert "st.page_link" not in rendered
    assert "👑" not in rendered
    assert "▣" not in rendered


def test_metric_help_is_formula_level_and_read_only():
    assert METRIC_HELP_VERSION == "metric-help-v3"
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
        assert f'metric_help("{key}"' in source
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


def test_main_projection_accepts_secondary_internal_tab_target():
    source = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    assert 'st.session_state.pop("projection_nav_target",None)' in source
    assert 'key="main_projection_navigation"' in source


def test_history_archive_and_actionable_scorecards_have_individual_help():
    source = (ROOT / "pages" / "4_Projection_History.py").read_text(encoding="utf-8")
    for key in (
        "history_archived_slates", "history_archived_pitchers", "history_manual_lines", "history_latest_slate",
        "history_ladder_calls", "history_ladder_wins", "history_ladder_win_rate", "history_crushers",
        "history_workload_snapshots", "history_pitch_mae", "history_bf_mae", "history_workload_outs_mae",
        "history_paired_outcomes", "history_helping_signals", "history_hurting_signals", "history_learning_signals",
    ):
        assert f'metric_help("{key}"' in source


def test_metric_help_v3_includes_current_value_and_limitation():
    text = metric_help("history_k_hit_rate", current="180/209 = 86.1%")
    assert "This box right now:" in text
    assert "180/209 = 86.1%" in text
    assert "What not to conclude:" in text
