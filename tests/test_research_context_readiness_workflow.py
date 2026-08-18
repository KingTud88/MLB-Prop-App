from pathlib import Path


WORKFLOW = Path(".github/workflows/research-context-readiness.yml")
BOT_PREFIX = "Automate projection capture and game resolution"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_research_readiness_allows_successful_non_push_resolver_runs() -> None:
    text = _text()
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.head_branch == 'main'" in text
    assert "github.event.workflow_run.event != 'push' ||" in text


def test_research_readiness_allows_user_triggered_push_run_even_if_head_message_moves() -> None:
    text = _text()
    assert "github.event.workflow_run.actor.login != 'github-actions[bot]' ||" in text


def test_research_readiness_keeps_bot_push_recursion_guard() -> None:
    text = _text()
    assert f"!startsWith(github.event.workflow_run.head_commit.message, '{BOT_PREFIX}')" in text
    assert "github.event.workflow_run.event != 'push' ||\n          github.event.workflow_run.actor.login != 'github-actions[bot]' ||\n          !startsWith" in text


def test_research_readiness_persists_freshness_outputs() -> None:
    text = _text()
    assert "python -m training.research_pipeline_freshness_audit" in text
    assert "data/research_pipeline_freshness_audit.csv" in text
    assert "data/research_pipeline_freshness_summary.csv" in text
