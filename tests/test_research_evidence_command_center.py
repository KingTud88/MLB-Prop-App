from __future__ import annotations

from pathlib import Path

import pandas as pd

from training.research_evidence_command_center import (
    NO_AUTO_PROMOTION,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    VERSION,
    build_command_center,
    build_summary,
)


def _write(root: Path, filename: str, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(root / filename, index=False)


def test_empty_archive_preserves_fixed_lane_registry_without_reconstruction(tmp_path: Path) -> None:
    center = build_command_center(tmp_path)
    assert len(center) == 13
    assert center["Lane"].nunique() == 13
    assert set(center["Status"]) == {"SOURCE_MISSING"}
    assert center["Report_Only"].all()
    assert set(center["Production_Authority"]) == {"NONE"}
    assert center["No_Auto_Promotion"].all()


def test_pitch_mix_reads_explicit_required_counts_from_source(tmp_path: Path) -> None:
    _write(tmp_path, "pitch_mix_whiff_forward_gate.csv", [{
        "Status": "LEARNING",
        "Resolved_Starts": 7,
        "Required_Starts": 60,
        "Resolved_Days": 2,
        "Required_Days": 10,
        "Opponents": 6,
        "Required_Opponents": 15,
        "Primary_Metric": "SPEARMAN_SCORE_DELTA_VS_K_RESIDUAL",
        "Reason": "frozen reason",
        "Recommended_Action": "COLLECT_FORWARD_OUTCOMES",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "Evaluation_Version": "eval-v1",
    }])
    center = build_command_center(tmp_path)
    row = center.loc[center["Lane"].eq("Pitch-Mix Whiff Forward")].iloc[0]
    assert row["Current_Starts"] == 7
    assert row["Required_Starts"] == 60
    assert row["Starts_Remaining"] == 53
    assert row["Current_Days"] == 2
    assert row["Required_Days"] == 10
    assert row["Days_Remaining"] == 8
    assert row["Current_Breadth"] == 6
    assert row["Required_Breadth"] == 15
    assert row["Breadth_Remaining"] == 9
    assert row["Ready_For_Manual_Review"] in (False, 0)


def test_confirmed_lineup_preserves_source_status_metrics_and_reason(tmp_path: Path) -> None:
    _write(tmp_path, "lineup_k_walkforward_gate.csv", [{
        "Evidence_Status": "LEARNING",
        "Authentic_Pregame_Pairs": 148,
        "OOS_Paired_Starts": 120,
        "Observed_Days": 5,
        "Distinct_Opponents": 30,
        "Relative_MAE_Improvement": 0.004864,
        "Confirmed_Win_Share": 0.516667,
        "Reason": "Need at least 30 OOS pairs, 10 observed days, and 8 opponents.",
        "Manual_Review_Ready": False,
        "Recommended_Action": "KEEP_LEARNING",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "Validation_Version": "lineup-v1",
    }])
    center = build_command_center(tmp_path)
    row = center.loc[center["Lane"].eq("Confirmed Lineup")].iloc[0]
    assert row["Status"] == "LEARNING"
    assert row["Current_Starts"] == 120
    assert row["Required_Starts"] == 30
    assert row["Starts_Remaining"] == 0
    assert row["Current_Days"] == 5
    assert row["Days_Remaining"] == 5
    assert row["Current_Breadth"] == 30
    assert row["Breadth_Remaining"] == 0
    assert "relative_mae=+0.49%" in row["Evidence_Direction"]
    assert row["Source_Reason"].startswith("Need at least 30 OOS pairs")


def test_derivation_early_reads_never_replace_forward_metrics(tmp_path: Path) -> None:
    _write(tmp_path, "opponent_matchup_asymmetric_response_shadow_gate.csv", [{
        "Finding": "INCONCLUSIVE",
        "Early_Read": "LEAN_SUPPORTED",
        "Forward_Starts": 25,
        "Forward_Days": 1,
        "Forward_Opponents": 24,
        "Forward_Changed_Starts": 9,
        "Forward_Boost_Capped_Starts": 7,
        "Forward_Weak_Reduce_Neutralized_Starts": 2,
        "Changed_Relative_MAE_vs_Applied": -0.0093589,
        "Changed_Win_Share_vs_Applied": 0.444444,
        "Candidate_Bias_Abs_Change_vs_Applied": -0.036,
        "Reason": "forward sample not mature",
        "Recommended_Action": "KEEP_COMPOSITE_FROZEN_AND_LEARN",
        "Manual_Review_Ready": False,
        "Report_Only": True,
        "Production_Authority": "NONE",
        "Validation_Version": "asymmetric-v1",
    }])
    _write(tmp_path, "lineup_materiality_shadow_gate.csv", [{
        "Finding": "INCONCLUSIVE",
        "Early_Read": "LEAN_SUPPORTED",
        "Forward_Pairs": 26,
        "Forward_Days": 1,
        "Forward_Opponents": 26,
        "Forward_Changed_Pairs": 21,
        "Changed_Relative_MAE_vs_Confirmed": -0.0058797,
        "Changed_Win_Share_vs_Confirmed": 0.380952,
        "Materiality_Relative_MAE_vs_Preconfirm": -0.0127783,
        "Materiality_Bias_Abs_Change_vs_Confirmed": -0.0193,
        "Reason": "forward sample not mature",
        "Recommended_Action": "KEEP_MATERIALITY_THRESHOLD_FROZEN_AND_LEARN",
        "Manual_Review_Ready": False,
        "Report_Only": True,
        "Production_Authority": "NONE",
        "Validation_Version": "materiality-v1",
    }])

    center = build_command_center(tmp_path)
    asymmetric = center.loc[center["Lane"].eq("Opponent Asymmetric Challenger")].iloc[0]
    materiality = center.loc[center["Lane"].eq("Lineup Materiality Shadow")].iloc[0]

    assert asymmetric["Status"] == "INCONCLUSIVE"
    assert "changed_relative_mae=-0.94%" in asymmetric["Evidence_Direction"]
    assert "changed_win_share=44.4%" in asymmetric["Evidence_Direction"]
    assert "LEAN_SUPPORTED" not in asymmetric["Evidence_Direction"]
    assert "derivation_read=LEAN_SUPPORTED" in asymmetric["Secondary_Progress"]

    assert materiality["Status"] == "INCONCLUSIVE"
    assert "changed_relative_mae=-0.59%" in materiality["Evidence_Direction"]
    assert "changed_win_share=38.1%" in materiality["Evidence_Direction"]
    assert "LEAN_SUPPORTED" not in materiality["Evidence_Direction"]
    assert "materiality_vs_preconfirm=-1.28%" in materiality["Secondary_Progress"]
    assert "derivation_read=LEAN_SUPPORTED" in materiality["Secondary_Progress"]


def test_umpire_k_up_cap_uses_forward_row_only(tmp_path: Path) -> None:
    _write(tmp_path, "umpire_k_up_cap_shadow_summary.csv", [
        {
            "Evidence_Lane": "DERIVATION_BACKTEST",
            "Evidence_Status": "DESCRIPTIVE_ONLY",
            "Eligible_Starts": 999,
            "Changed_Starts": 999,
            "Observed_Days": 99,
            "Distinct_Umpires": 99,
            "Capped_Relative_MAE_vs_Incumbent": 0.50,
            "Capped_Win_Share_vs_Incumbent": 0.99,
            "Frozen_Max_K_Up_Factor": 1.015,
            "Reason": "derivation only",
            "Recommended_Action": "DO_NOT_COUNT",
            "Manual_Review_Ready": False,
            "Report_Only": True,
            "Production_Authority": "NONE",
            "Validation_Version": "umpire-cap-v1",
        },
        {
            "Evidence_Lane": "FORWARD_OOS",
            "Evidence_Status": "LEARNING",
            "Eligible_Starts": 15,
            "Changed_Starts": 7,
            "Observed_Days": 3,
            "Distinct_Umpires": 6,
            "Capped_Relative_MAE_vs_Incumbent": 0.006,
            "Capped_Win_Share_vs_Incumbent": 0.57,
            "Frozen_Max_K_Up_Factor": 1.015,
            "Reason": "Need 30 forward changed starts, 10 days, and 12 umpires.",
            "Recommended_Action": "KEEP_K_UP_CAP_SHADOW_FROZEN_AND_LEARN",
            "Manual_Review_Ready": False,
            "Report_Only": True,
            "Production_Authority": "NONE",
            "Validation_Version": "umpire-cap-v1",
        },
    ])
    center = build_command_center(tmp_path)
    row = center.loc[center["Lane"].eq("Umpire K-UP Cap Shadow")].iloc[0]
    assert row["Status"] == "LEARNING"
    assert row["Current_Starts"] == 7
    assert row["Required_Starts"] == 30
    assert row["Starts_Remaining"] == 23
    assert row["Current_Days"] == 3
    assert row["Days_Remaining"] == 7
    assert row["Current_Breadth"] == 6
    assert row["Required_Breadth"] == 12
    assert row["Breadth_Remaining"] == 6
    assert "relative_mae=+0.60%" in row["Evidence_Direction"]
    assert "win_share=57.0%" in row["Evidence_Direction"]
    assert "eligible_starts=15" in row["Secondary_Progress"]
    assert "frozen_max_factor=1.015" in row["Secondary_Progress"]
    assert "999" not in str(row.to_dict())
    assert row["Ready_For_Manual_Review"] in (False, 0)
    assert row["Production_Authority"] == "NONE"


def test_catcher_context_surfaces_maturity_without_changing_source_gate(tmp_path: Path) -> None:
    _write(tmp_path, "catcher_context_validation_gate.csv", [{
        "Evidence_Status": "LEARNING",
        "Authentic_Pregame_Resolved": 36,
        "Auditable_Starts": 0,
        "Observed_Days": 0,
        "Distinct_Catchers": 0,
        "Reason": "Need at least 30 auditable starts, 8 catchers, and 10 days; have 0, 0, and 0.",
        "Recommended_Activation": False,
        "Report_Only": True,
        "Production_Authority": "NONE",
        "Validation_Version": "catcher-v1",
    }])
    _write(tmp_path, "catcher_prior_maturity_summary.csv", [{
        "Known_Resolved_Catchers": 64,
        "Resolved_Context_Starts": 156,
        "Next_Appearance_Ready_No_Auditable_Yet": 1,
        "Near_Ready_3_4": 28,
        "Report_Only": True,
        "Production_Authority": "NONE",
        "Maturity_Version": "maturity-v1",
    }])

    center = build_command_center(tmp_path)
    row = center.loc[center["Lane"].eq("Catcher Context")].iloc[0]
    assert row["Status"] == "LEARNING"
    assert row["Current_Starts"] == 0
    assert row["Current_Breadth"] == 0
    assert row["Ready_For_Manual_Review"] in (False, 0)
    assert row["Recommended_Action"] == "KEEP_LEARNING"
    assert row["Production_Authority"] == "NONE"
    assert "authentic_pregame_resolved=36" in row["Secondary_Progress"]
    assert "resolved_pool=64 catchers/156 starts" in row["Secondary_Progress"]
    assert "next_appearance_ready=1" in row["Secondary_Progress"]
    assert "near_ready_3_4=28" in row["Secondary_Progress"]

    _write(tmp_path, "catcher_prior_maturity_summary.csv", [{
        "Known_Resolved_Catchers": 999,
        "Resolved_Context_Starts": 999,
        "Next_Appearance_Ready_No_Auditable_Yet": 999,
        "Near_Ready_3_4": 999,
        "Report_Only": False,
        "Production_Authority": "LIVE",
    }])
    blocked = build_command_center(tmp_path)
    blocked_row = blocked.loc[blocked["Lane"].eq("Catcher Context")].iloc[0]
    assert "maturity_context=CONTROL_BLOCKED" in blocked_row["Secondary_Progress"]
    assert "999" not in blocked_row["Secondary_Progress"]
    assert blocked_row["Current_Starts"] == 0
    assert blocked_row["Ready_For_Manual_Review"] in (False, 0)
    assert blocked_row["Production_Authority"] == "NONE"


def test_top_plays_uses_only_overall_real_line_row(tmp_path: Path) -> None:
    _write(tmp_path, "top_plays_accountability_summary.csv", [
        {
            "Dimension": "RANK",
            "Segment": "1",
            "Settled Legs": 1,
            "Observed Days": 1,
            "Hit Rate": 0.0,
            "Calibration Gap": 0.8,
            "Brier Score": 0.7,
            "Evidence": "LEARNING",
            "Reason": "rank row",
            "Report Only": True,
            "Production Authority": "NONE",
            "Accountability Version": "tp-v1",
        },
        {
            "Dimension": "OVERALL",
            "Segment": "ALL REAL-LINE TOP PLAYS",
            "Settled Legs": 5,
            "Observed Days": 1,
            "Hit Rate": 0.6,
            "Calibration Gap": 0.1835,
            "Brier Score": 0.2927,
            "Evidence": "LEARNING",
            "Reason": "Need 20 settled real-line Top Plays in this segment; 5 available.",
            "Report Only": True,
            "Production Authority": "NONE",
            "Accountability Version": "tp-v1",
        },
    ])
    center = build_command_center(tmp_path)
    row = center.loc[center["Lane"].eq("Top Plays Accountability")].iloc[0]
    assert row["Current_Starts"] == 5
    assert row["Required_Starts"] == 20
    assert row["Starts_Remaining"] == 15
    assert "hit_rate=60.0%" in row["Evidence_Direction"]
    assert "calibration_gap=+18.35%" in row["Evidence_Direction"]


def test_calibration_aggregates_existing_gate_results_without_new_decision_rule(tmp_path: Path) -> None:
    _write(tmp_path, "calibration_shadow_gate.csv", [
        {"Milestone": 3, "OOS_Starts": 107, "Promotion_Gate_Status": "FAIL", "Reasons": "brier", "Gate_Version": "cal-v1"},
        {"Milestone": 4, "OOS_Starts": 107, "Promotion_Gate_Status": "FAIL", "Reasons": "win_share", "Gate_Version": "cal-v1"},
    ])
    center = build_command_center(tmp_path)
    row = center.loc[center["Lane"].eq("Calibration Shadow")].iloc[0]
    assert row["Status"] == "FAIL"
    assert row["Current_Starts"] == 107
    assert row["Evidence_Direction"] == "milestones_pass=0/2; milestones_fail=2/2"
    assert row["Ready_For_Manual_Review"] in (False, 0)
    assert row["Production_Authority"] == "NONE"
    assert row["No_Auto_Promotion"] in (True, 1)


def test_summary_is_operational_only_not_a_composite_research_score(tmp_path: Path) -> None:
    center = build_command_center(tmp_path)
    summary = build_summary(center).iloc[0]
    assert summary["Total_Lanes"] == 13
    assert summary["Source_Missing_Lanes"] == 13
    assert summary["All_Report_Only"] in (True, 1)
    assert summary["All_Production_Authority_None"] in (True, 1)
    assert summary["No_Auto_Promotion"] in (True, 1)
    assert "Locked_Promotion_Scoreboard_Cards" not in summary.index
    assert "Score" not in summary.index


def test_current_repository_evidence_sources_are_readable_and_non_authoritative() -> None:
    center = build_command_center(Path("data"))
    summary = build_summary(center).iloc[0]
    assert len(center) == 13
    assert summary["Source_Missing_Lanes"] == 0
    assert summary["All_Report_Only"] in (True, 1)
    assert summary["All_Production_Authority_None"] in (True, 1)
    assert center["No_Auto_Promotion"].all()
    assert set(center["Production_Authority"]) == {"NONE"}


def test_command_center_contract_is_report_only_without_presentation_lock() -> None:
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert NO_AUTO_PROMOTION is True
    assert VERSION == "research-evidence-command-center-v1-report-only"
