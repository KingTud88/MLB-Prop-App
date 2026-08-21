from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/umpire-history-backfill.yml")
BACKFILL_SCRIPT = Path("automation/backfill_umpire_history.py")
OBSERVATION_LOG = Path("data/umpire_observation_log.csv")
DAILY_RESOLVER = Path(".github/workflows/daily-projection-resolver.yml")


def test_completed_umpire_backfill_workflow_stays_retired() -> None:
    assert not WORKFLOW.exists()
    assert BACKFILL_SCRIPT.is_file()
    assert OBSERVATION_LOG.is_file()


def test_daily_resolver_remains_the_live_umpire_capture_path() -> None:
    source = DAILY_RESOLVER.read_text(encoding="utf-8")
    assert "Capture report-only pregame umpire context" in source
    assert "python automation/umpire_context_capture.py" in source
    assert "tests/test_umpire_context.py" in source
    assert "tests/test_umpire_k_live_validation.py" in source
