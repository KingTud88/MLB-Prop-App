from pathlib import Path

from engine.explainability_ui import metric_help


ROOT = Path(__file__).resolve().parents[1]


def test_secondary_sidebar_uses_projection_parity_icons_and_compact_brand():
    nav = (ROOT / "navigation.py").read_text(encoding="utf-8")
    assert "PROJECTION_PARITY_SIDEBAR_V16" in nav
    assert "render_sidebar_brand" in nav
    assert "st.radio(" in nav
    assert "format_func=lambda key: NAV_ITEMS[key]" in nav
    for icon in ("◎", "▥", "⌁", "◉", "▣", "◉", "ϟ", "♔"):
        assert icon in nav


def test_secondary_pages_no_longer_use_old_page_link_sidebar_shell():
    nav = (ROOT / "navigation.py").read_text(encoding="utf-8")
    assert "st.page_link" not in nav
    assert "SECONDARY_COMPACT_SIDEBAR_V2" not in nav
    assert "width:252px!important" not in nav


def test_history_metric_boxes_have_individual_help_keys():
    source = (ROOT / "pages/4_Projection_History.py").read_text(encoding="utf-8")
    for key in (
        "history_archived_slates", "history_archived_pitchers", "history_manual_lines", "history_latest_slate",
        "history_evidence_rows", "history_resolved_games", "history_k_range_hits", "history_k_hit_rate",
        "history_hits_range_hits", "history_hits_hit_rate", "history_outs_range_hits", "history_outs_hit_rate",
        "history_k_mae", "history_hits_mae", "history_outs_mae",
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


def test_automatic_evidence_separates_range_coverage_from_execution_grades():
    source = (ROOT / "pages/4_Projection_History.py").read_text(encoding="utf-8")
    assert 'return "✅ IN RANGE"' in source
    assert 'else "❌ OUTSIDE"' in source
    assert 'TextColumn("80% K Range")' in source
    assert 'TextColumn("80% Hits Range")' in source
    assert 'TextColumn("80% Outs Range")' in source
    assert 'TextColumn("Hits Result")' not in source
    assert 'TextColumn("Outs Result")' not in source
    assert "Model diagnostics and execution evidence are intentionally separate" in source
    assert "Hits/Outs Line + Side + Bet Result = true execution history" in source
    assert "Execution evidence never feeds calibration or projection training" in source
    assert 'TextColumn("Hits Bet Result")' in source
    assert 'TextColumn("Outs Bet Result")' in source
    assert 'K coverage rate' in source
    assert 'Hits coverage rate' in source
    assert 'Outs coverage rate' in source


def test_evidence_metric_help_uses_coverage_language():
    for key in ("history_k_hit_rate", "history_hits_hit_rate", "history_outs_hit_rate"):
        text = metric_help(key)
        assert "intervals covered" in text
        assert "coverage" in text.lower()
