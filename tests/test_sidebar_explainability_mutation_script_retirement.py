from __future__ import annotations

from pathlib import Path


MUTATION_SCRIPT = Path(".github/scripts/sidebar_explainability_v14.py")
NAVIGATION = Path("navigation.py")
EXPLAINABILITY_UI = Path("engine/explainability_ui.py")
WORKFLOWS = Path(".github/workflows")


def test_obsolete_sidebar_explainability_mutation_script_stays_retired() -> None:
    assert not MUTATION_SCRIPT.exists()
    for workflow in WORKFLOWS.glob("*.yml"):
        assert "sidebar_explainability_v14.py" not in workflow.read_text(encoding="utf-8")


def test_current_sidebar_and_metric_help_versions_remain_authoritative() -> None:
    navigation = NAVIGATION.read_text(encoding="utf-8")
    explainability = EXPLAINABILITY_UI.read_text(encoding="utf-8")
    assert "PROJECTION_PARITY_SIDEBAR_V3" in navigation
    assert 'METRIC_HELP_VERSION = "metric-help-v3"' in explainability
