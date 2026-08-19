from pathlib import Path


WORKFLOW = Path(".github/workflows/research-context-readiness.yml")
RESOLVER = Path(".github/workflows/daily-projection-resolver.yml")
RUNNER = "bash automation/research_context_readiness.sh"
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


def test_research_readiness_has_no_cross_workflow_or_reusable_dependency() -> None:
    text = _workflow_text()
    assert "workflow_run:" not in text
    assert "workflow_call:" not in text
    assert "github.event.workflow_run" not in text


def test_daily_resolver_runs_research_job_only_after_projection_success() -> None:
    text = _resolver_text()
    block = text.split("  research-context-readiness:\n", 1)[1]
    assert "    needs: projection-log" in block
    assert "    if: needs.projection-log.result == 'success'" in block
    assert "    permissions:\n      contents: write\n" in block
    assert "    runs-on: ubuntu-latest" in block
    assert RUNNER in block
    assert "uses: ./.github/workflows/research-context-readiness.yml" not in block


def test_resolver_bot_push_guard_prevents_research_commit_recursion() -> None:
    text = _resolver_text()
    assert f"!startsWith(github.event.head_commit.message, '{BOT_PREFIX}')" in text
    assert "needs.projection-log.result == 'success'" in text


def test_fallback_workflow_uses_same_shared_runner() -> None:
    text = _workflow_text()
    assert RUNNER in text
    assert "  workflow_dispatch:" in text
    for cron in FALLBACK_CRONS:
        assert f'- cron: "{cron}"' in text
    assert text.count("- cron:") == len(FALLBACK_CRONS)


def test_both_research_paths_have_write_permission() -> None:
    workflow = _workflow_text()
    resolver = _resolver_text().split("  research-context-readiness:\n", 1)[1]
    assert "permissions:\n  contents: write" in workflow
    assert "permissions:\n      contents: write" in resolver
