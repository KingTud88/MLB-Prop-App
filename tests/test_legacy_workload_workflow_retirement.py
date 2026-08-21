from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
DATA = ROOT / "data"


def test_legacy_workload_mutation_workflows_stay_retired() -> None:
    for filename in (
        "workload-v21-validation.yml",
        "workload-v22-validation.yml",
        "workload-v23-validation.yml",
    ):
        assert not (WORKFLOWS / filename).exists()


def test_negative_workload_evidence_is_preserved_and_current_lane_remains_available() -> None:
    for filename in (
        "workload_v21_summary.csv",
        "workload_v22_summary.csv",
        "workload_v23_summary.csv",
    ):
        assert (DATA / filename).exists()

    assert (WORKFLOWS / "workload-v25-validation.yml").exists()
    assert (DATA / "workload_v25_summary.csv").exists()
