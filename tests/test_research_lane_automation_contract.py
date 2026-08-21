from pathlib import Path


RESOLVER = Path(".github/workflows/daily-projection-resolver.yml")
SHARED = Path("automation/research_context_readiness.sh")
CAL_V2 = Path(".github/workflows/calibration-common-mode-v2.yml")
WORKLOAD_V25 = Path(".github/workflows/workload-v25-validation.yml")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_daily_resolver_refreshes_every_base_lane_source_that_needs_daily_outcomes() -> None:
    text = _read(RESOLVER)
    required_modules = (
        "training.live_role_shadow_gate",
        "training.calibration_shadow_gate",
        "training.ml_shadow_report",
        "training.top_plays_accountability",
        "training.catcher_context_validation",
        "training.lineup_k_walkforward",
        "training.lineup_materiality_shadow",
        "training.umpire_k_live_validation",
        "training.umpire_k_up_cap_shadow",
        "training.opponent_matchup_validation",
        "training.handedness_matchup_audit",
        "training.opponent_matchup_boost_stress",
        "training.opponent_matchup_reduce_stress",
        "training.opponent_matchup_weak_reduce_neutral_shadow",
        "training.opponent_matchup_asymmetric_response_shadow",
        "training.opponent_matchup_boost_cap_shadow",
    )
    for module in required_modules:
        assert module in text
    assert "RESEARCH_CONTEXT_NO_PUSH=1 bash automation/research_context_readiness.sh" in text


def test_shared_research_runner_advances_context_and_residual_lanes() -> None:
    text = _read(SHARED)
    required_modules = (
        "training.handedness_matchup_audit",
        "training.pitch_arsenal_capture",
        "training.batter_pitch_whiff_capture",
        "training.pitch_mix_readiness_audit",
        "training.pitch_mix_whiff_score_capture",
        "training.pitch_mix_whiff_forward_evaluation",
        "training.projection_crusher_shadow",
        "training.projection_underperformer_shadow",
        "training.k_ladder_reliability_shadow",
        "training.input_quality_matched_v2",
        "training.catcher_prior_maturity",
        "training.umpire_k_up_cap_shadow",
        "training.research_promotion_command_center",
        "training.research_pipeline_freshness_audit",
    )
    for module in required_modules:
        assert module in text


def test_calibration_common_mode_v2_has_its_own_scheduled_report_only_refresh() -> None:
    text = _read(CAL_V2)
    assert "schedule:" in text
    assert "python -m training.calibration_common_mode_v2" in text
    assert "data/calibration_common_mode_v2_summary.csv" in text
    assert "git push origin HEAD:main" in text


def test_workload_v25_remains_isolated_historical_report_only_replay() -> None:
    text = _read(WORKLOAD_V25)
    assert "workflow_dispatch:" in text
    assert "workload-v25-metric-gate" in text
    assert "python -m training.workload_v25_metric_gate_backtest" in text
    assert "git push origin HEAD:workload-v25-metric-gate" in text
    assert "git push origin HEAD:main" not in text
