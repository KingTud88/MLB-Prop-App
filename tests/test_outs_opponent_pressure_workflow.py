from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_outs_opponent_pressure_workflow_is_independent_and_report_only():
    text = (ROOT / ".github" / "workflows" / "outs-opponent-pressure-audit.yml").read_text(encoding="utf-8")
    assert "training.outs_opponent_pressure_capture" in text
    assert "training.outs_opponent_pressure_audit" in text
    assert "training.research_signal_coverage_audit" in text
    assert "data/outs_opponent_pressure_context_log.csv" in text
    assert "data/outs_opponent_pressure_gate.csv" in text
    assert "research_pipeline_freshness_audit" not in text
    assert "research_promotion_command_center" not in text
    assert "projection_engine" not in text
    assert "Top Plays" not in text


def test_workflow_pushes_with_rebase_and_never_force_pushes():
    text = (ROOT / ".github" / "workflows" / "outs-opponent-pressure-audit.yml").read_text(encoding="utf-8")
    assert "git fetch origin main" in text
    assert "git rebase origin/main" in text
    assert "git push origin HEAD:main" in text
    assert "--force" not in text
