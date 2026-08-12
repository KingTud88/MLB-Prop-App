from pathlib import Path


def test_projection_history_has_walk_forward_health_dashboard():
    source = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")
    compile(source, "pages/4_Projection_History.py", "exec")
    assert "Walk-forward Top 5 model health" in source
    assert "walk_forward_top5(df)" in source
    assert "health_from_walk_forward" in source
    assert "Probability reliability — walk-forward Top 5" in source
    assert "Daily historical Top 5 replay" in source


def test_top_plays_applies_health_before_ranking():
    source = Path("pages/6_Top_Plays.py").read_text(encoding="utf-8")
    compile(source, "pages/6_Top_Plays.py", "exec")
    assert "walk_forward = walk_forward_top5(history)" in source
    assert "health_report = health_from_walk_forward(walk_forward)" in source
    assert "decision_report = decision_tier_report(walk_forward)" in source
    assert "market_health=health_map" in source
    assert '"Model Health"' in source
    assert "BLOCKED and is removed before today's Top 5 is ranked" in source
