from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def test_retired_engine_upgrade_workflow_cannot_be_dispatched() -> None:
    assert not (WORKFLOWS / "upgrade-engine-3-1.yml").exists()
    assert not (ROOT / "scripts" / "upgrade_engine_3_1.py").exists()

    workflow_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(WORKFLOWS.glob("*.yml"))
    )
    assert "upgrade_engine_3_1.py" not in workflow_text
    assert ".upgrade_engine_3_1" not in workflow_text


def test_live_operational_workflows_remain_present() -> None:
    for filename in (
        "quality.yml",
        "daily-projection-resolver.yml",
        "research-context-readiness.yml",
    ):
        assert (WORKFLOWS / filename).exists()
