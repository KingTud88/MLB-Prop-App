from __future__ import annotations

from pathlib import Path

import pandas as pd

from training.research_evidence_command_center import (
    LOCKED_PROMOTION_SCOREBOARD_CARDS,
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
    assert len(center) == 12
    assert center["Lane"].nunique() == 12
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
    assert summary["Total_Lanes"] == 12
    assert summary["Source_Missing_Lanes"] == 12
    assert summary["All_Report_Only"] in (True, 1)
    assert summary["All_Production_Authority_None"] in (True, 1)
    assert summary["No_Auto_Promotion"] in (True, 1)
    assert summary["Locked_Promotion_Scoreboard_Cards"] == 8
    assert "Score" not in summary.index


def test_command_center_contract_is_report_only_and_preserves_locked_scoreboard() -> None:
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert NO_AUTO_PROMOTION is True
    assert LOCKED_PROMOTION_SCOREBOARD_CARDS == 8
    assert VERSION == "research-evidence-command-center-v1-report-only"
