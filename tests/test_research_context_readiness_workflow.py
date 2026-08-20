from pathlib import Path


WORKFLOW = Path(".github/workflows/research-context-readiness.yml")
RESOLVER = Path(".github/workflows/daily-projection-resolver.yml")
RUNNER = "bash automation/research_context_readiness.sh"
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


def test_daily_resolver_is_schedule_or_manual_only() -> None:
    text = _resolver_text()
    trigger_block = text.split("permissions:", 1)[0]
    assert "\n  push:" not in trigger_block
    assert "  schedule:" in trigger_block
    assert "  workflow_dispatch:" in trigger_block
    assert "github.event_name" not in text
    assert "github.event.head_commit" not in text


def test_daily_resolver_runs_research_sequentially_and_defers_push() -> None:
    text = _resolver_text()
    assert "  research-context-readiness:" not in text
    assert text.count(RUNNER) == 1
    assert "run: RESEARCH_CONTEXT_NO_PUSH=1 " + RUNNER in text
    projection_commit = text.index('git commit -m "Automate projection capture and game resolution"')
    research_refresh = text.index("RESEARCH_CONTEXT_NO_PUSH=1 " + RUNNER)
    final_push = text.index("      - name: Push all resolver and research updates once")
    assert projection_commit < research_refresh < final_push
    pre_research = text[projection_commit:research_refresh]
    assert "git push origin HEAD:main" not in pre_research
    assert text[final_push:].count("git push origin HEAD:main") == 1
    assert "    timeout-minutes: 40" in text


def test_projection_no_change_path_does_not_exit_before_research_refresh() -> None:
    text = _resolver_text()
    start = text.index("      - name: Commit updated projection")
    end = text.index("      - name: Refresh and persist report-only research context")
    commit_block = text[start:end]
    assert "git diff --cached --quiet" in commit_block
    assert "exit 0" not in commit_block


def test_fallback_workflow_uses_same_runner_and_skips_recent_primary_refresh() -> None:
    text = _workflow_text()
    assert RUNNER in text
    assert "  workflow_dispatch:" in text
    for cron in FALLBACK_CRONS:
        assert f'- cron: "{cron}"' in text
    assert text.count("- cron:") == len(FALLBACK_CRONS)
    assert '--since="90 minutes ago"' in text
    assert '--grep="^Automate projection capture and game resolution: refresh research context readiness$"' in text
    assert text.count("if: steps.primary-refresh.outputs.skip != 'true'") == 3


def test_both_research_paths_have_write_permission() -> None:
    workflow = _workflow_text()
    resolver = _resolver_text()
    assert "permissions:\n  contents: write" in workflow
    assert "permissions:\n  contents: write" in resolver
