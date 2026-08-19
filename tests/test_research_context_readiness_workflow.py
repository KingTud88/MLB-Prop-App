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


def test_daily_resolver_runs_research_sequentially_in_projection_job() -> None:
    text = _resolver_text()
    assert "  research-context-readiness:" not in text
    assert text.count(RUNNER) == 1
    assert "      - name: Refresh and persist report-only research context\n        run: " + RUNNER in text
    assert text.index("git commit -m \"Automate projection capture and game resolution\"") < text.index(RUNNER)
    assert "    timeout-minutes: 40" in text


def test_projection_no_change_path_does_not_exit_before_research_refresh() -> None:
    text = _resolver_text()
    start = text.index("      - name: Commit updated projection")
    end = text.index("      - name: Refresh and persist report-only research context")
    commit_block = text[start:end]
    assert "git diff --cached --quiet" in commit_block
    assert "exit 0" not in commit_block


def test_resolver_bot_push_guard_prevents_research_commit_recursion() -> None:
    text = _resolver_text()
    assert f"!startsWith(github.event.head_commit.message, '{BOT_PREFIX}')" in text


def test_fallback_workflow_uses_same_shared_runner() -> None:
    text = _workflow_text()
    assert RUNNER in text
    assert "  workflow_dispatch:" in text
    for cron in FALLBACK_CRONS:
        assert f'- cron: "{cron}"' in text
    assert text.count("- cron:") == len(FALLBACK_CRONS)


def test_both_research_paths_have_write_permission() -> None:
    workflow = _workflow_text()
    resolver = _resolver_text()
    assert "permissions:\n  contents: write" in workflow
    assert "permissions:\n  contents: write" in resolver
