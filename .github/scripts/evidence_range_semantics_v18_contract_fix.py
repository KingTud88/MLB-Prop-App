from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

path = ROOT / "tests" / "test_hits_allowed_ui_contract.py"
text = path.read_text(encoding="utf-8")
old = '''def test_projection_history_grades_hits_allowed():\n    source = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")\n    for token in (\n        "hits_projection",\n        "hits_range_low",\n        "hits_range_high",\n        "actual_hits_allowed",\n        "hits_result",\n        "Hits hit rate",\n    ):\n        assert token in source\n'''
new = '''def test_projection_history_tracks_hits_allowed_range_coverage():\n    source = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")\n    for token in (\n        "hits_projection",\n        "hits_range_low",\n        "hits_range_high",\n        "actual_hits_allowed",\n        "hits_result",\n        "Hits coverage rate",\n        'TextColumn("80% Hits Range")',\n        "✅ IN RANGE",\n        "❌ OUTSIDE",\n    ):\n        assert token in source\n    assert 'TextColumn("Hits Result")' not in source\n'''
if old not in text:
    raise SystemExit("Hits Allowed stale contract anchor not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

path = ROOT / "tests" / "test_projection_history_learning_dashboard.py"
text = path.read_text(encoding="utf-8")
old = '    assert "80% Range Result" in text\n'
new = '''    assert 'TextColumn("80% K Range")' in text\n    assert 'TextColumn("80% Hits Range")' in text\n    assert 'TextColumn("80% Outs Range")' in text\n    assert "K Target / K Result is the only WIN/MISS lane" in text\n'''
if old not in text:
    raise SystemExit("Projection History stale 80% range contract anchor not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

print("evidence_range_semantics_v18 stale contracts refreshed")
