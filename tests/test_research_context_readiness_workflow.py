from pathlib import Path


WORKFLOW = Path(".github/workflows/research-context-readiness.yml")
RESOLVER = Path(".github/workflows/daily-projection-resolver.yml")
BOT_PREFIX = "Automate projection capture and game resolution"
FALLBACK_CRONS = (
    "15 14 * * *",
    "15 17 * * *",
    "15 19 * * *",
    "15 21 * * *",
    "15 23 * * *",
    "15 3 * * *",
)


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _resolver_text() -> str:
    return RESOLVER.read_text(encoding="utf-8")


def test_research_readiness_is_reusable_without_workflow_run_dependency() -> None:
    text = _workflow_text()
    assert "  workflow_call:" in text
    assert "workflow_run:" not in text
    assert "github.event.workflow_run" not in text


def test_daily_resolver_calls_research_readiness_only_after_success() -> None:
    text = _resolver_text()
    assert "  research-context-readiness:" in text
    assert "    needs: projection-log" in text
    assert "    if: needs.projection-log.result == 'success'" in text
    assert "    uses: ./.github/workflows/research-context-readiness.yml" in text


def test_daily_resolver_passes_write_permission_to_reusable_research_job() -> None:
    text = _resolver_text()
    block = text.split("  research-context-readiness:\n", 1)[1]
    assert "    permissions:\n      contents: write\n" in block


def test_resolver_bot_push_guard_prevents_research_commit_recursion() -> None:
    text = _resolver_text()
    assert f"!startsWith(github.event.head_commit.message, '{BOT_PREFIX}')" in text
    assert "needs.projection-log.result == 'success'" in text


def test_research_readiness_has_one_hour_later_fallback_for_every_resolver_window() -> None:
    text = _workflow_text()
    for cron in FALLBACK_CRONS:
        assert f'- cron: "{cron}"' in text
    assert text.count("- cron:") == len(FALLBACK_CRONS)


def test_research_readiness_keeps_manual_dispatch_and_freshness_outputs() -> None:
    text = _workflow_text()
    assert "  workflow_dispatch:" in text
    assert "python -m training.research_pipeline_freshness_audit" in text
    assert "data/research_pipeline_freshness_audit.csv" in text
    assert "data/research_pipeline_freshness_summary.csv" in text
