from __future__ import annotations

from pathlib import Path

import pandas as pd

from training.research_promotion_command_center import (
    SCOREBOARD_MODE,
    build_promotion_command_center,
    build_summary,
)


def _write(data_dir: Path, name: str, row: dict[str, object]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row]).to_csv(data_dir / name, index=False)


def test_promotion_command_center_shows_all_base_and_new_shadow_lanes(tmp_path: Path) -> None:
    center = build_promotion_command_center(tmp_path)
    lanes = set(center["Lane"].astype(str))

    assert len(center) == 16
    assert "Pitch-Mix Whiff Forward" in lanes
    assert "Opponent Asymmetric Challenger" in lanes
    assert "Projection Crusher Shadow" in lanes
    assert "Projection Underperformer Shadow" in lanes
    assert "K Ladder Reliability Shadow" in lanes
    assert set(center["Production_Authority"].astype(str)) == {"NONE"}
    assert center["Report_Only"].astype(bool).all()
    assert center["No_Auto_Promotion"].astype(bool).all()

    summary = build_summary(center).iloc[0]
    assert summary["Total_Lanes"] == 16
    assert summary["Scoreboard_Mode"] == SCOREBOARD_MODE == "ALL_LANES"
    assert bool(summary["All_Report_Only"])
    assert bool(summary["All_Production_Authority_None"])
    assert bool(summary["No_Auto_Promotion"])


def test_new_shadow_lane_verdicts_are_source_owned_not_regraded(tmp_path: Path) -> None:
    _write(tmp_path, "projection_crusher_shadow_gate.csv", {
        "Status": "LEARNING",
        "Resolved_Starts": 44,
        "Required_Starts": 60,
        "Resolved_Days": 6,
        "Required_Days": 10,
        "Distinct_Pitchers": 18,
        "Required_Pitchers": 20,
        "Beat_Projection_Rate": 0.59,
        "Material_Crusher_Rate": 0.18,
        "Mean_K_Residual": 0.21,
        "Cohorts_Tracked": 9,
        "Ready_For_Manual_Review": False,
        "Recommended_Action": "COLLECT_EXACT_PROJECTION_CRUSHER_EVIDENCE",
        "Reason": "native Crusher gate reason",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "Research_Version": "crusher-test",
    })
    _write(tmp_path, "projection_underperformer_shadow_gate.csv", {
        "Status": "LEARNING",
        "Resolved_Starts": 44,
        "Required_Starts": 60,
        "Resolved_Days": 6,
        "Required_Days": 10,
        "Distinct_Pitchers": 18,
        "Required_Pitchers": 20,
        "Below_Projection_Rate": 0.55,
        "Material_Underperform_Rate": 0.20,
        "Mean_K_Residual": -0.17,
        "Cohorts_Tracked": 8,
        "Ready_For_Manual_Review": False,
        "Recommended_Action": "COLLECT_EXACT_PROJECTION_UNDERPERFORMER_EVIDENCE",
        "Reason": "native underperformer gate reason",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "Research_Version": "underperformer-test",
    })
    _write(tmp_path, "k_ladder_reliability_shadow_gate.csv", {
        "Status": "READY_FOR_MANUAL_RESEARCH_REVIEW",
        "Resolved_Calls": 70,
        "Required_Calls": 60,
        "Resolved_Days": 11,
        "Required_Days": 10,
        "Distinct_Pitchers": 24,
        "Required_Pitchers": 20,
        "Probability_Coverage": 0.95,
        "Required_Probability_Coverage": 0.80,
        "Ladder_Win_Rate": 0.63,
        "Avg_Target_Probability": 0.66,
        "Calibration_Gap": 0.03,
        "Brier_Score": 0.22,
        "Cohorts_Tracked": 10,
        "Ready_For_Manual_Review": True,
        "Recommended_Action": "MANUAL_RESEARCH_REVIEW",
        "Reason": "native ladder gate reason",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "Research_Version": "ladder-test",
    })

    center = build_promotion_command_center(tmp_path).set_index("Lane")
    assert center.loc["Projection Crusher Shadow", "Status"] == "LEARNING"
    assert center.loc["Projection Crusher Shadow", "Source_Reason"] == "native Crusher gate reason"
    assert center.loc["Projection Underperformer Shadow", "Status"] == "LEARNING"
    assert center.loc["Projection Underperformer Shadow", "Source_Reason"] == "native underperformer gate reason"
    assert center.loc["Projection Underperformer Shadow", "Production_Authority"] == "NONE"
    assert center.loc["K Ladder Reliability Shadow", "Status"] == "READY_FOR_MANUAL_RESEARCH_REVIEW"
    assert bool(center.loc["K Ladder Reliability Shadow", "Ready_For_Manual_Review"])
    assert center.loc["K Ladder Reliability Shadow", "Recommended_Action"] == "MANUAL_RESEARCH_REVIEW"
    assert center.loc["K Ladder Reliability Shadow", "Production_Authority"] == "NONE"
