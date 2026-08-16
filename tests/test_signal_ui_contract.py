from pathlib import Path


def test_top_plays_attaches_signal_evidence_after_model_board():
    source = Path("pages/6_Top_Plays.py").read_text(encoding="utf-8")
    build_pos = source.index("plays = build_model_board(slate, history, limit=5, market_health=health_map, require_market_lines=True)")
    attach_pos = source.index("plays = attach_signal_profiles(plays, history, signal_report)")
    assert attach_pos > build_pos
    assert "attached after ranking and cannot reorder or remove today's legs" in source
    assert "Signal Evidence" in source


def test_projection_history_exposes_paired_signal_accountability():
    source = Path("pages/4_Projection_History.py").read_text(encoding="utf-8")
    assert "🧪 Signal accountability" in source
    assert "paired_signal_report(df)" in source
    assert "context_performance_report(df)" in source
    assert "Weather Delay Risk is labeled CONTEXT ONLY" in source


def test_lineup_refresh_preserves_hits_before_after_evidence():
    source = Path("automation/daily_projection_runner.py").read_text(encoding="utf-8")
    for field in (
        "lineup_preconfirm_hits_projection",
        "lineup_preconfirm_opponent_hit_rate",
        "lineup_hits_projection_delta",
        "lineup_opponent_hit_delta",
    ):
        assert field in source
