from __future__ import annotations

from pathlib import Path

import pandas as pd

from training.input_quality_matched_v2 import PRIMARY_RULE
from training.research_promotion_command_center import (
    SCOREBOARD_MODE,
    build_promotion_command_center,
    build_summary,
)


def _write(data_dir: Path, name: str, rows: dict[str, object] | list[dict[str, object]]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = rows if isinstance(rows, list) else [rows]
    pd.DataFrame(payload).to_csv(data_dir / name, index=False)


def test_promotion_command_center_registers_full_research_program_inventory(tmp_path: Path) -> None:
    center = build_promotion_command_center(tmp_path)
    lanes = set(center["Lane"].astype(str))
    expected = {
        "Opponent Asymmetric Challenger",
        "Opponent BOOST Cap Shadow",
        "Weak-REDUCE Neutralization Shadow",
        "Confirmed Lineup",
        "Lineup Materiality Shadow",
        "Handedness Matchup Audit",
        "Pitch-Mix Whiff Forward",
        "Umpire Context",
        "Umpire K-UP Cap Shadow",
        "Catcher Context",
        "Calibration Shadow",
        "Starter Role Live Shadow",
        "Top Plays Accountability",
        "Projection Crusher Shadow",
        "Projection Underperformer Shadow",
        "K Ladder Reliability Shadow",
        "Input Quality v2 · Strikeouts",
        "Input Quality v2 · Hits",
        "Input Quality v2 · Outs",
        "Calibration Common-Mode v2",
        "ML Challenger",
        "Workload v2.5 Candidates",
    }
    assert expected.issubset(lanes)
    assert len(center) >= len(expected)
    assert center["Lane"].is_unique
    assert set(center["Production_Authority"].astype(str)) == {"NONE"}
    assert center["Report_Only"].astype(bool).all()
    assert center["No_Auto_Promotion"].astype(bool).all()

    summary = build_summary(center).iloc[0]
    assert int(summary["Total_Lanes"]) == len(center)
    assert summary["Scoreboard_Mode"] == SCOREBOARD_MODE == "ALL_LANES"
    assert bool(summary["All_Report_Only"])
    assert bool(summary["All_Production_Authority_None"])
    assert bool(summary["No_Auto_Promotion"])


def test_exact_projection_shadow_verdicts_remain_source_owned(tmp_path: Path) -> None:
    _write(tmp_path, "projection_crusher_shadow_gate.csv", {
        "Status": "LEARNING", "Resolved_Starts": 44, "Required_Starts": 60,
        "Resolved_Days": 6, "Required_Days": 10, "Distinct_Pitchers": 18,
        "Required_Pitchers": 20, "Beat_Projection_Rate": 0.59,
        "Material_Crusher_Rate": 0.18, "Mean_K_Residual": 0.21,
        "Cohorts_Tracked": 9, "Ready_For_Manual_Review": False,
        "Recommended_Action": "COLLECT_EXACT_PROJECTION_CRUSHER_EVIDENCE",
        "Reason": "native Crusher gate reason", "Report_Only": True,
        "Production_Authority": "NONE", "Research_Version": "crusher-test",
    })
    _write(tmp_path, "projection_underperformer_shadow_gate.csv", {
        "Status": "LEARNING", "Resolved_Starts": 44, "Required_Starts": 60,
        "Resolved_Days": 6, "Required_Days": 10, "Distinct_Pitchers": 18,
        "Required_Pitchers": 20, "Below_Projection_Rate": 0.55,
        "Material_Underperform_Rate": 0.20, "Mean_K_Residual": -0.17,
        "Cohorts_Tracked": 8, "Ready_For_Manual_Review": False,
        "Recommended_Action": "COLLECT_EXACT_PROJECTION_UNDERPERFORMER_EVIDENCE",
        "Reason": "native underperformer gate reason", "Report_Only": True,
        "Production_Authority": "NONE", "Research_Version": "underperformer-test",
    })
    _write(tmp_path, "k_ladder_reliability_shadow_gate.csv", {
        "Status": "READY_FOR_MANUAL_RESEARCH_REVIEW", "Resolved_Calls": 70,
        "Required_Calls": 60, "Resolved_Days": 11, "Required_Days": 10,
        "Distinct_Pitchers": 24, "Required_Pitchers": 20,
        "Probability_Coverage": 0.95, "Required_Probability_Coverage": 0.80,
        "Ladder_Win_Rate": 0.63, "Avg_Target_Probability": 0.66,
        "Calibration_Gap": 0.03, "Brier_Score": 0.22, "Cohorts_Tracked": 10,
        "Ready_For_Manual_Review": True, "Recommended_Action": "MANUAL_RESEARCH_REVIEW",
        "Reason": "native ladder gate reason", "Report_Only": True,
        "Production_Authority": "NONE", "Research_Version": "ladder-test",
    })
    center = build_promotion_command_center(tmp_path).set_index("Lane")
    assert center.loc["Projection Crusher Shadow", "Status"] == "LEARNING"
    assert center.loc["Projection Crusher Shadow", "Source_Reason"] == "native Crusher gate reason"
    assert center.loc["Projection Underperformer Shadow", "Status"] == "LEARNING"
    assert center.loc["Projection Underperformer Shadow", "Source_Reason"] == "native underperformer gate reason"
    assert center.loc["K Ladder Reliability Shadow", "Status"] == "READY_FOR_MANUAL_RESEARCH_REVIEW"
    assert bool(center.loc["K Ladder Reliability Shadow", "Ready_For_Manual_Review"])
    assert center.loc["K Ladder Reliability Shadow", "Production_Authority"] == "NONE"


def test_input_quality_v2_registers_each_primary_metric_without_aggregating_verdicts(tmp_path: Path) -> None:
    rows = []
    for metric, status, pairs in (
        ("STRIKEOUTS", "SUPPORTIVE", 24),
        ("HITS", "LEARNING", 12),
        ("OUTS", "CONTRADICTORY", 22),
    ):
        rows.append({
            "Audit_Version": "input-quality-matched-v2-report-only",
            "Production_Authority": "NONE", "Rule": PRIMARY_RULE.name,
            "Metric": metric, "Eligible_Shallow": 30, "Eligible_Deep": 50,
            "Matched_Pairs": pairs, "Shallow_MAE": 2.0, "Deep_MAE": 1.9,
            "Relative_MAE_Improvement_Deep_vs_Shallow": 0.05,
            "Shallow_Bias": 0.2, "Deep_Bias": 0.1, "Status": status,
            "Future_Only_Start": "2026-08-20", "Min_Matched_Pairs": 20,
        })
    _write(tmp_path, "input_quality_matched_v2_summary.csv", rows)
    center = build_promotion_command_center(tmp_path).set_index("Lane")
    assert center.loc["Input Quality v2 · Strikeouts", "Status"] == "SUPPORTIVE"
    assert center.loc["Input Quality v2 · Hits", "Status"] == "LEARNING"
    assert center.loc["Input Quality v2 · Outs", "Status"] == "CONTRADICTORY"
    assert set(center.loc[[
        "Input Quality v2 · Strikeouts", "Input Quality v2 · Hits", "Input Quality v2 · Outs"
    ], "Production_Authority"].astype(str)) == {"NONE"}


def test_calibration_common_mode_v2_enters_manual_review_only_after_source_helping_verdict(tmp_path: Path) -> None:
    _write(tmp_path, "calibration_common_mode_v2_summary.csv", {
        "Audit_Version": "calibration-common-mode-v2-report-only",
        "Production_Authority": "NONE", "Future_Only_Start": "2026-08-21",
        "Eligible_Future_Starts": 35, "OOS_Starts": 32, "Evidence_Days": 6,
        "Distinct_Pitchers": 18, "Baseline_MAE": 1.8, "Candidate_MAE": 1.75,
        "Relative_MAE_Improvement": 0.0278, "Baseline_Bias": 0.2,
        "Candidate_Bias": 0.1, "Candidate_Win_Share": 0.54,
        "Tie_Rate": 0.0, "Status": "HELPING",
    })
    row = build_promotion_command_center(tmp_path).set_index("Lane").loc["Calibration Common-Mode v2"]
    assert row["Status"] == "HELPING"
    assert bool(row["Ready_For_Manual_Review"])
    assert row["Recommended_Action"] == "MANUAL_RESEARCH_REVIEW_ONLY"
    assert row["Production_Authority"] == "NONE"


def test_ml_negative_evidence_is_preserved_as_a_visible_lane(tmp_path: Path) -> None:
    _write(tmp_path, "ml_shadow_summary.csv", [
        {
            "Challenger": "ML_SHADOW", "OOS_Starts": 189, "Existing_MAE": 1.82,
            "Candidate_MAE": 2.03, "Relative_MAE_Improvement": -0.1127,
            "Candidate_Win_Share": 0.444, "Existing_Bias": 0.16,
            "Candidate_Bias": 0.03, "Status": "MIXED", "Reason": "guardrail",
            "Report_Only": True, "Live_Projection_Use": False,
            "Market_Features_Used": False, "Validation_Version": "ml-test",
        },
        {
            "Challenger": "SIM_MATH_ML_EQUAL_THIRDS", "OOS_Starts": 101,
            "Relative_MAE_Improvement": -0.01, "Candidate_Win_Share": 0.47,
            "Status": "MIXED", "Report_Only": True,
        },
    ])
    row = build_promotion_command_center(tmp_path).set_index("Lane").loc["ML Challenger"]
    assert row["Status"] == "MIXED"
    assert "relative_mae=-11.27%" in row["Evidence_Direction"]
    assert row["Recommended_Action"] == "PRESERVE_NEGATIVE_ML_EVIDENCE_NO_PROMOTION"
    assert row["Production_Authority"] == "NONE"


def test_workload_lane_fails_closed_without_cross_season_decisions(tmp_path: Path) -> None:
    _write(tmp_path, "workload_v25_summary.csv", [
        {"Season": 2026, "Metric": "PITCHES", "Evaluated_Starts": 2032, "Relative_MAE_vs_v23": 0.0077, "V25_Adjusted_Starts": 312, "V25_Win_Share_vs_v23": 0.654, "V25_Status": "MIXED", "Candidate_Version": "v25-test"},
        {"Season": 2026, "Metric": "BF", "Evaluated_Starts": 2032, "Relative_MAE_vs_v23": 0.0019, "V25_Adjusted_Starts": 312, "V25_Win_Share_vs_v23": 0.551, "V25_Status": "MIXED", "Candidate_Version": "v25-test"},
        {"Season": 2026, "Metric": "OUTS", "Evaluated_Starts": 2032, "Relative_MAE_vs_v23": 0.0013, "V25_Adjusted_Starts": 312, "V25_Win_Share_vs_v23": 0.542, "V25_Status": "MIXED", "Candidate_Version": "v25-test"},
    ])
    row = build_promotion_command_center(tmp_path).set_index("Lane").loc["Workload v2.5 Candidates"]
    assert row["Source_Path"] == "data/workload_promotion_decisions.csv"
    assert row["Status"] == "SOURCE_MISSING"
    assert row["Recommended_Action"] == "REFRESH_REPORT_ONLY_RESEARCH_SOURCE"
    assert not bool(row["Ready_For_Manual_Review"])
    assert row["Production_Authority"] == "NONE"
