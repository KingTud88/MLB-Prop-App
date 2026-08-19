from pathlib import Path


RUNNER = Path("automation/research_context_readiness.sh")


def _text() -> str:
    return RUNNER.read_text(encoding="utf-8")


def test_runner_keeps_one_shared_refresh_timestamp() -> None:
    text = _text()
    assert "RESEARCH_REFRESH_AT_UTC" in text
    assert '--observed-at-utc "${RESEARCH_REFRESH_AT_UTC}"' in text
    assert '--refresh-at-utc "${RESEARCH_REFRESH_AT_UTC}"' in text
    assert '--queued-at-utc "${RESEARCH_REFRESH_AT_UTC}"' in text


def test_runner_orders_dependency_chain_before_freshness_audit() -> None:
    text = _text()
    stages = (
        "training.umpire_k_up_cap_shadow",
        "training.umpire_context_review_snapshot",
        "training.confirmed_lineup_review_snapshot",
        "training.research_review_snapshot_freshness",
        "training.research_evidence_command_center",
        "training.research_milestone_watch",
        "training.research_evidence_history",
        "training.research_evidence_transition_digest",
        "training.research_manual_review_packet",
        "training.research_multicell_review_injector",
        "training.research_manual_review_queue",
        "training.research_pipeline_freshness_audit",
    )
    positions = [text.index(stage) for stage in stages]
    assert positions == sorted(positions)


def test_runner_persists_freshness_review_watch_and_shadow_outputs() -> None:
    text = _text()
    expected = (
        "data/umpire_k_up_cap_shadow_detail.csv",
        "data/umpire_k_up_cap_shadow_summary.csv",
        "data/umpire_context_review_snapshot.csv",
        "data/umpire_context_review_summary.csv",
        "data/confirmed_lineup_review_snapshot.csv",
        "data/confirmed_lineup_review_summary.csv",
        "data/research_review_snapshot_freshness.csv",
        "data/research_review_snapshot_freshness_summary.csv",
        "data/research_evidence_command_center.csv",
        "data/research_milestone_watch.csv",
        "data/research_milestone_watch_summary.csv",
        "data/research_evidence_history.csv",
        "data/research_evidence_transition_digest.csv",
        "data/research_manual_review_packet.csv",
        "data/research_manual_review_queue.csv",
        "data/research_pipeline_freshness_audit.csv",
        "data/research_pipeline_freshness_summary.csv",
    )
    for path in expected:
        assert path in text


def test_runner_keeps_report_only_contract_tests_in_path() -> None:
    text = _text()
    assert "tests/test_umpire_k_up_cap_shadow.py" in text
    assert "tests/test_umpire_context_review_snapshot.py" in text
    assert "tests/test_umpire_context_review_pipeline.py" in text
    assert "tests/test_confirmed_lineup_review_snapshot.py" in text
    assert "tests/test_research_review_snapshot_freshness.py" in text
    assert "tests/test_research_milestone_watch.py" in text
    assert "tests/test_research_multicell_review_injector.py" in text
    assert "tests/test_research_pipeline_freshness_audit.py" in text
    assert "tests/test_research_evidence_command_center.py" in text
    assert "tests/test_research_manual_review_queue.py" in text
    assert 'git commit -m "Automate projection capture and game resolution: refresh research context readiness"' in text
