from pathlib import Path


def test_projection_history_renders_research_promotion_scoreboard_after_evidence_scoreboard() -> None:
    text = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")
    assert "from engine.research_promotion_scoreboard import render_research_promotion_scoreboard" in text
    assert "render_research_promotion_scoreboard(ROOT)" in text
    evidence = text.index('label="ⓘ EXPLAIN EVIDENCE SCOREBOARD"')
    board = text.index("render_research_promotion_scoreboard(ROOT)")
    k_research = text.index("K research diagnostics")
    assert evidence < board < k_research


def test_projection_history_separates_ladder_and_exact_projection_crusher_semantics() -> None:
    text = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")
    assert "K Ladder Reliability & Projection Crushers" in text
    assert "5.07 projected and 5 actual Ks is a ladder win but an exact-projection miss" in text
    assert "Projection Crushers · exact frozen projection" in text
    assert "Avg K vs Projection" in text
    assert "Total K Above Projection" in text
    assert "Crusher margin = Actual Ks − exact frozen Projected Ks" in text
    assert "Neither signal is sportsbook execution grading" in text
    assert "Bettable K Wins & Crushers" not in text


def test_research_scoreboard_is_report_only_and_source_owned() -> None:
    text = Path("engine/research_promotion_scoreboard.py").read_text(encoding="utf-8")
    assert "Native research verdicts are displayed as written by each validator" in text
    assert "Production Authority" in text
    assert "The scoreboard does not recalculate them" in text
    assert "cannot change the live baseball projection" in text


def test_research_scoreboard_density_polish_keeps_gate_progress_primary_and_authority_compact() -> None:
    text = Path("engine/research_promotion_scoreboard.py").read_text(encoding="utf-8")
    assert ".research-card{min-height:198px" in text
    assert "research-label-gate" in text
    assert "research-value-gate" in text
    assert "research-authority-strip" in text
    assert '<span class="research-authority-label">Production authority</span>' in text
    assert "research-value-sample" in text
    assert "research-value-action" in text
