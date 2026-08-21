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


def test_runner_orders_research_sources_before_control_plane_and_freshness() -> None:
    text = _text()
    stages = (
        "training.input_quality_matched_v2",
        "training.umpire_k_up_cap_shadow",
        "training.umpire_context_review_snapshot",
        "training.confirmed_lineup_review_snapshot",
        "training.research_review_snapshot_freshness",
        "training.research_evidence_command_center",
        "training.research_promotion_command_center",
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


def test_runner_routes_milestones_history_and_review_packet_through_all_lane_promotion_center() -> None:
    text = _text()
    command_center_arg = "--command-center data/research_promotion_command_center.csv"
    assert text.count(command_center_arg) == 3
    milestone_pos = text.index("training.research_milestone_watch")
    history_pos = text.index("training.research_evidence_history")
    packet_pos = text.index("training.research_manual_review_packet")
    first_arg_pos = text.index(command_center_arg, milestone_pos)
    second_arg_pos = text.index(command_center_arg, history_pos)
    third_arg_pos = text.index(command_center_arg, packet_pos)
    assert milestone_pos < first_arg_pos < history_pos < second_arg_pos < packet_pos < third_arg_pos


def test_runner_persists_freshness_review_watch_and_shadow_outputs() -> None:
    text = _text()
    expected = (
        "data/projection_crusher_shadow_detail.csv",
        "data/projection_crusher_shadow_pitchers.csv",
        "data/projection_crusher_shadow_cohorts.csv",
        "data/projection_crusher_shadow_gate.csv",
        "data/projection_underperformer_shadow_detail.csv",
        "data/projection_underperformer_shadow_pitchers.csv",
        "data/projection_underperformer_shadow_cohorts.csv",
        "data/projection_underperformer_shadow_gate.csv",
        "data/k_ladder_reliability_shadow_detail.csv",
        "data/k_ladder_reliability_shadow_cohorts.csv",
        "data/k_ladder_reliability_shadow_gate.csv",
        "data/input_quality_matched_v2_pairs.csv",
        "data/input_quality_matched_v2_summary.csv",
        "data/input_quality_matched_v2_preregistration.csv",
        "data/umpire_k_up_cap_shadow_detail.csv",
        "data/umpire_k_up_cap_shadow_summary.csv",
        "data/umpire_context_review_snapshot.csv",
        "data/umpire_context_review_summary.csv",
        "data/confirmed_lineup_review_snapshot.csv",
        "data/confirmed_lineup_review_summary.csv",
        "data/research_review_snapshot_freshness.csv",
        "data/research_review_snapshot_freshness_summary.csv",
        "data/research_evidence_command_center.csv",
        "data/research_promotion_command_center.csv",
        "data/research_promotion_command_center_summary.csv",
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
    expected_tests = (
        "tests/test_projection_crushers.py",
        "tests/test_projection_crusher_shadow.py",
        "tests/test_projection_underperformer_shadow.py",
        "tests/test_k_ladder_reliability_shadow.py",
        "tests/test_input_quality_matched_v2.py",
        "tests/test_calibration_common_mode_v2.py",
        "tests/test_umpire_k_up_cap_shadow.py",
        "tests/test_umpire_context_review_snapshot.py",
        "tests/test_umpire_context_review_pipeline.py",
        "tests/test_confirmed_lineup_review_snapshot.py",
        "tests/test_research_review_snapshot_freshness.py",
        "tests/test_research_promotion_command_center.py",
        "tests/test_research_promotion_scoreboard.py",
        "tests/test_research_milestone_watch.py",
        "tests/test_research_multicell_review_injector.py",
        "tests/test_research_pipeline_freshness_audit.py",
        "tests/test_research_evidence_command_center.py",
        "tests/test_research_manual_review_queue.py",
    )
    for test_path in expected_tests:
        assert test_path in text
    assert 'git commit -m "Automate projection capture and game resolution: refresh research context readiness"' in text


def test_runner_advances_input_quality_before_building_promotion_center() -> None:
    text = _text()
    input_quality_pos = text.index("PYTHONPATH=. python -m training.input_quality_matched_v2")
    promotion_pos = text.index("PYTHONPATH=. python -m training.research_promotion_command_center")
    assert input_quality_pos < promotion_pos
    assert "PYTHONPATH=. python -m training.calibration_common_mode_v2" not in text


def test_runner_supports_deferred_push_for_primary_resolver() -> None:
    text = _text()
    commit_pos = text.index(
        'git commit -m "Automate projection capture and game resolution: refresh research context readiness"'
    )
    deferred_pos = text.index('if [ "${RESEARCH_CONTEXT_NO_PUSH:-0}" = "1" ]; then')
    push_pos = text.index("git push origin HEAD:main")
    assert commit_pos < deferred_pos < push_pos
    assert "Research context committed locally; caller owns final push." in text
