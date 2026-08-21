from pathlib import Path


RUNNER = Path("automation/research_context_readiness.sh")


def test_governance_v2_runs_after_promotion_center_before_milestones() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    promotion = text.index("PYTHONPATH=. python -m training.research_promotion_command_center")
    governance = text.index("PYTHONPATH=. python -m training.research_governance_v2")
    milestone = text.index("PYTHONPATH=. python -m training.research_milestone_watch")
    assert promotion < governance < milestone


def test_governance_v2_contract_tests_are_in_shared_refresh() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    for test_path in (
        "tests/test_research_governance_v2.py",
        "tests/test_research_direction_flip_review.py",
        "tests/test_calibration_shadow_governance_metadata.py",
        "tests/test_research_governance_pipeline_contract.py",
    ):
        assert test_path in text


def test_governance_v2_outputs_are_persisted() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    for path in (
        "data/research_hypothesis_manifest.csv",
        "data/research_uncertainty_v2.csv",
        "data/research_governance_v2_summary.csv",
    ):
        assert path in text


def test_governance_v2_does_not_enter_production_or_execution_paths() -> None:
    text = Path("training/research_governance_v2.py").read_text(encoding="utf-8")
    lowered = text.lower()
    assert 'PRODUCTION_AUTHORITY = "NONE"' in text
    assert "AUTOMATIC_DECISION_ALLOWED = False" in text
    assert "sportsbook" not in lowered
    assert "bet_log" not in lowered
    assert "from engine.projection" not in lowered
    assert "import engine.projection" not in lowered
    assert "data/projection_log.csv" not in lowered
    assert "data/bet_log.csv" not in lowered
    assert "streamlit" not in lowered
