from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
TRAINING = ROOT / "training"
DATA = ROOT / "data"


def test_stale_live_role_diagnostic_workflow_stays_retired() -> None:
    assert not (WORKFLOWS / "live-role-capture-diagnostic.yml").exists()


def test_live_role_research_pipeline_and_historical_diagnostic_stay_preserved() -> None:
    assert (TRAINING / "live_role_capture_diagnostic.py").exists()
    assert (DATA / "live_role_capture_diagnostic.csv").exists()
    assert (TRAINING / "live_role_shadow_evidence.py").exists()
    assert (TRAINING / "live_role_shadow_gate.py").exists()

    resolver = (WORKFLOWS / "daily-projection-resolver.yml").read_text(encoding="utf-8")
    assert "python -m training.live_role_shadow_evidence" in resolver
    assert "python -m training.live_role_shadow_gate" in resolver
    assert "data/live_role_shadow_gate.csv" in resolver
