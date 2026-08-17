from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# History helpers now include a dynamic `current=` argument, so the contract
# should assert the helper key rather than require an immediate closing paren.
path = ROOT / "tests" / "test_sidebar_metric_explainability_v2.py"
text = path.read_text(encoding="utf-8")
old = '''    for key in keys:\n        assert f'metric_help("{key}")' in source\n'''
new = '''    for key in keys:\n        assert f'metric_help("{key}"' in source\n'''
if old not in text:
    raise SystemExit("History metric-help contract anchor not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

# The old compact page-link sidebar is intentionally retired. Secondary pages
# now use the same eight-option radio language and vector icon treatment as the
# Main Projection rail.
path = ROOT / "tests" / "test_ui_theme_contract.py"
text = path.read_text(encoding="utf-8")
old = '''def test_sidebar_has_compact_custom_navigation():\n    source = Path("navigation.py").read_text(encoding="utf-8")\n    assert "SECONDARY_COMPACT_SIDEBAR_V2" in source\n    assert "sk-nav-compact-crown" in source\n    assert "sk-nav-compact-script" in source\n    assert "sk-nav-compact-king" in source\n    assert "CLE-themed MLB starter projection engine" in source\n    assert 'render_sidebar(active: str = "projection")' in source\n    rendered = source[source.index("with st.sidebar:"):]\n    assert "sk-nav-mascot" not in rendered\n    for label in ("Projection", "Top Plays", "Bet Tracker", "Projection History", "Daily Projection Run"):\n        assert label in source\n'''
new = '''def test_sidebar_matches_main_projection_navigation_language():\n    source = Path("navigation.py").read_text(encoding="utf-8")\n    assert "PROJECTION_PARITY_SIDEBAR_V3" in source\n    assert "render_sidebar_brand()" in source\n    assert 'render_sidebar(active: str = "projection")' in source\n    assert "st.radio(" in source\n    assert 'label:nth-child(8)::before' in source\n    for label in (\n        "Projection", "Distribution", "Form & Workload", "Model Card",\n        "Bet Tracker", "Projection History", "Daily Projection Run", "Top Plays",\n    ):\n        assert label in source\n    rendered = source[source.index("# PROJECTION_PARITY_SIDEBAR_V3"):]\n    assert "st.page_link" not in rendered\n    assert "sk-nav-compact-crown" not in rendered\n    assert "👑" not in rendered\n'''
if old not in text:
    raise SystemExit("Legacy sidebar contract anchor not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

print("V16 stale UI contracts refreshed")
