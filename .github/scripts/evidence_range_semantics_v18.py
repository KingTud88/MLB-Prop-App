from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

page_path = ROOT / "pages" / "4_Projection_History.py"
page = page_path.read_text(encoding="utf-8")

replacements = {
    '    return "✅ HIT" if float(row[low_col]) <= actual <= float(row[high_col]) else "❌ MISS"\n':
        '    return "✅ IN RANGE" if float(row[low_col]) <= actual <= float(row[high_col]) else "❌ OUTSIDE"\n',
    'col3.metric("K range hits", k_hit_count, help=metric_help("history_k_range_hits", current=f"{k_hit_count}/{k_ready_count} eligible K intervals contained the final Ks"))':
        'col3.metric("K intervals covered", k_hit_count, help=metric_help("history_k_range_hits", current=f"{k_hit_count}/{k_ready_count} eligible K intervals contained the final Ks"))',
    'col4.metric("K hit rate", f"{k_hit_rate:.1%}" if k_hit_rate is not None else "—", help=metric_help("history_k_hit_rate", current=(f"{k_hit_count}/{k_ready_count} = {k_hit_rate:.1%}" if k_hit_rate is not None else "No eligible resolved K intervals yet")))':
        'col4.metric("K coverage rate", f"{k_hit_rate:.1%}" if k_hit_rate is not None else "—", help=metric_help("history_k_hit_rate", current=(f"{k_hit_count}/{k_ready_count} = {k_hit_rate:.1%}" if k_hit_rate is not None else "No eligible resolved K intervals yet")))',
    'col5.metric("Hits range hits", h_hit_count, help=metric_help("history_hits_range_hits", current=f"{h_hit_count}/{h_ready_count} eligible Hits intervals contained the final result"))':
        'col5.metric("Hits intervals covered", h_hit_count, help=metric_help("history_hits_range_hits", current=f"{h_hit_count}/{h_ready_count} eligible Hits intervals contained the final result"))',
    'col6.metric("Hits hit rate", f"{h_hit_rate:.1%}" if h_hit_rate is not None else "—", help=metric_help("history_hits_hit_rate", current=(f"{h_hit_count}/{h_ready_count} = {h_hit_rate:.1%}" if h_hit_rate is not None else "No eligible resolved Hits intervals yet")))':
        'col6.metric("Hits coverage rate", f"{h_hit_rate:.1%}" if h_hit_rate is not None else "—", help=metric_help("history_hits_hit_rate", current=(f"{h_hit_count}/{h_ready_count} = {h_hit_rate:.1%}" if h_hit_rate is not None else "No eligible resolved Hits intervals yet")))',
    'outs_metrics1.metric("Outs range hits", o_hit_count, help=metric_help("history_outs_range_hits", current=f"{o_hit_count}/{o_ready_count} eligible Outs intervals contained the final result"))':
        'outs_metrics1.metric("Outs intervals covered", o_hit_count, help=metric_help("history_outs_range_hits", current=f"{o_hit_count}/{o_ready_count} eligible Outs intervals contained the final result"))',
    'outs_metrics2.metric("Outs hit rate", f"{o_hit_rate:.1%}" if o_hit_rate is not None else "—", help=metric_help("history_outs_hit_rate", current=(f"{o_hit_count}/{o_ready_count} = {o_hit_rate:.1%}" if o_hit_rate is not None else "No eligible resolved Outs intervals yet")))':
        'outs_metrics2.metric("Outs coverage rate", f"{o_hit_rate:.1%}" if o_hit_rate is not None else "—", help=metric_help("history_outs_hit_rate", current=(f"{o_hit_count}/{o_ready_count} = {o_hit_rate:.1%}" if o_hit_rate is not None else "No eligible resolved Outs intervals yet")))',
    'st.caption("ⓘ Every scorecard now has its own info icon. 80% range HIT means the final result landed inside that market\'s frozen pregame interval; MAE measures average miss size.")':
        'st.caption("ⓘ Every scorecard now has its own info icon. 80% range coverage means the final result landed inside that market\'s frozen pregame interval; it is not a sportsbook win/loss grade. MAE measures average miss size.")',
    '    "k_range_result": st.column_config.TextColumn("80% Range Result"),':
        '    "k_range_result": st.column_config.TextColumn("80% K Range"),',
    '    "hits_result": st.column_config.TextColumn("Hits Result"),':
        '    "hits_result": st.column_config.TextColumn("80% Hits Range"),',
    '    "outs_result": st.column_config.TextColumn("Outs Result"),':
        '    "outs_result": st.column_config.TextColumn("80% Outs Range"),',
    'st.caption("Click a date to open that slate. Inside each date: pitcher/matchup → projected K → bettable K target → actual Ks → WIN/MISS → exact-model and 80% range diagnostics. Empty None/null/NaN columns are hidden automatically.")':
        'st.caption("Click a date to open that slate. K Target / K Result is the only WIN/MISS lane in this automatic evidence table. The 80% K, Hits, and Outs Range columns only show whether the final MLB result landed inside the frozen model interval; they are not sportsbook bet grades. Hits/Outs are never graded as bets here without a saved sportsbook line + side. Empty None/null/NaN columns are hidden automatically.")',
}

for old, new in replacements.items():
    if old not in page:
        raise SystemExit(f"Projection History anchor not found: {old[:100]!r}")
    page = page.replace(old, new, 1)
page_path.write_text(page, encoding="utf-8")

help_path = ROOT / "engine" / "explainability_ui.py"
help_text = help_path.read_text(encoding="utf-8")
help_replacements = {
    '            "Formula: K range hits ÷ resolved rows with actual Ks + both frozen K range bounds.\\n\\n"':
        '            "Formula: K intervals covered ÷ resolved rows with actual Ks + both frozen K range bounds.\\n\\n"',
    '            "Formula: Hits range hits ÷ resolved rows with actual Hits Allowed + both frozen Hits range bounds.\\n\\n"':
        '            "Formula: Hits intervals covered ÷ resolved rows with actual Hits Allowed + both frozen Hits range bounds.\\n\\n"',
    '            "Formula: Outs range hits ÷ resolved rows with actual Outs + both frozen Outs range bounds.\\n\\n"':
        '            "Formula: Outs intervals covered ÷ resolved rows with actual Outs + both frozen Outs range bounds.\\n\\n"',
}
for old, new in help_replacements.items():
    if old not in help_text:
        raise SystemExit(f"Explainability anchor not found: {old!r}")
    help_text = help_text.replace(old, new, 1)
help_path.write_text(help_text, encoding="utf-8")

test_path = ROOT / "tests" / "test_sidebar_metric_explainability_v2.py"
test = test_path.read_text(encoding="utf-8")
marker = "\ndef test_automatic_evidence_uses_range_coverage_not_bet_grades():\n"
if marker not in test:
    test += '''\n\ndef test_automatic_evidence_uses_range_coverage_not_bet_grades():\n    source = (ROOT / "pages/4_Projection_History.py").read_text(encoding="utf-8")\n    assert 'return "✅ IN RANGE"' in source\n    assert 'else "❌ OUTSIDE"' in source\n    assert 'TextColumn("80% K Range")' in source\n    assert 'TextColumn("80% Hits Range")' in source\n    assert 'TextColumn("80% Outs Range")' in source\n    assert 'TextColumn("Hits Result")' not in source\n    assert 'TextColumn("Outs Result")' not in source\n    assert 'K Target / K Result is the only WIN/MISS lane' in source\n    assert 'without a saved sportsbook line + side' in source\n    assert 'K coverage rate' in source\n    assert 'Hits coverage rate' in source\n    assert 'Outs coverage rate' in source\n\n\ndef test_evidence_metric_help_uses_coverage_language():\n    for key in ("history_k_hit_rate", "history_hits_hit_rate", "history_outs_hit_rate"):\n        text = metric_help(key)\n        assert "intervals covered" in text\n        assert "coverage" in text.lower()\n'''
test_path.write_text(test, encoding="utf-8")

print("evidence_range_semantics_v18 applied")
