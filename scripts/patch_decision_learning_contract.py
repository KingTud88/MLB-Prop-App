from pathlib import Path

path = Path("tests/test_walk_forward_health_ui.py")
text = path.read_text(encoding="utf-8")
old = '''    assert "market_health_report(history)" in source
    assert "market_health=health_map" in source
'''
new = '''    assert "walk_forward = walk_forward_top5(history)" in source
    assert "health_report = health_from_walk_forward(walk_forward)" in source
    assert "decision_report = decision_tier_report(walk_forward)" in source
    assert "market_health=health_map" in source
'''
if old not in text:
    raise SystemExit("walk-forward Top Plays contract anchor missing")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
