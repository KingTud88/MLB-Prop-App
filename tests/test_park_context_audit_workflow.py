from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_park_context_workflow_is_independent_report_only_refresh():
    workflow = (ROOT / ".github" / "workflows" / "park-context-audit.yml").read_text()

    assert "python -m training.park_context_audit --refresh-missing-source" in workflow
    assert "tests/test_park_context_audit.py" in workflow
    assert "tests/test_research_signal_coverage_audit.py" in workflow
    assert "data/park_context_preregistration.csv" in workflow
    assert "data/park_context_statcast_source.csv" in workflow
    assert "data/park_context_forward_detail.csv" in workflow
    assert "data/park_context_forward_summary.csv" in workflow
    assert "data/park_context_gate.csv" in workflow
    assert "streamlit_app.py" not in workflow
    assert "projection_engine.py" not in workflow
    assert "research_promotion_command_center.csv" not in workflow
    assert "research_context_readiness.sh" not in workflow
    assert "git push origin HEAD:main" in workflow
