from pathlib import Path


def test_projection_history_surfaces_decision_learning_scoreboard():
    source = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")
    assert "🎯 Decision-learning tiers" in source
    assert "decision_tier_report(walk_forward)" in source
    assert "Sportsbook odds, sportsbook edge, book choice, and saved bet selections are excluded" in source
    assert "STRONG EVIDENCE" in source
    assert "UNDERPERFORMING" in source


def test_top_plays_attaches_decision_evidence_without_ranking_by_it():
    source = Path("pages/6_Top_Plays.py").read_text(encoding="utf-8")
    assert "attach_decision_profiles(plays, decision_report)" in source
    assert '"Decision Evidence"' in source
    assert '"Decision Sample"' in source
    assert '"Tier Hit Rate"' in source
    assert "decision evidence is descriptive only" in source
    assert "walk_forward = walk_forward_top5(history)" in source
    assert "market_health_map(health_report)" in source


def test_decision_learning_pages_compile():
    for page in ["pages/4_Projection_History.py", "pages/6_Top_Plays.py"]:
        source = Path(page).read_text(encoding="utf-8")
        compile(source, page, "exec")
