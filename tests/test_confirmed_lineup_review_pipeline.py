from __future__ import annotations

import pandas as pd

from training.confirmed_lineup_review_snapshot import build_review_snapshot, build_review_summary
from training.research_manual_review_packet import build_manual_review_packet

REFRESH = "2026-08-25T14:00:00+00:00"


def _segments() -> pd.DataFrame:
    return pd.DataFrame([{
        "Dimension": "OVERALL",
        "Segment": "ALL CONFIRMED LINEUP PAIRS",
        "Rows": 200,
        "Authentic_Pregame_Pairs": 180,
        "OOS_Paired_Starts": 160,
        "Observed_Days": 10,
        "Distinct_Opponents": 30,
        "Preconfirm_MAE": 1.75,
        "Confirmed_MAE": 1.74,
        "Relative_MAE_Improvement": 0.0057,
        "Confirmed_Win_Share": 0.525,
        "Confirmed_Loss_Share": 0.475,
        "Preconfirm_Bias": 0.10,
        "Confirmed_Bias": 0.11,
        "Mean_Absolute_Projection_Delta": 0.09,
        "Evidence": "SUPPORTED",
        "Reason": "Minimum frozen evaluation gate is mature.",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "Validation_Version": "lineup-k-walkforward-v2-lineage-safe-report-only",
    }])


def _gate() -> pd.DataFrame:
    return pd.DataFrame([{
        "Evidence_Status": "SUPPORTED",
        "OOS_Paired_Starts": 160,
        "Observed_Days": 10,
        "Distinct_Opponents": 30,
        "Preconfirm_MAE": 1.75,
        "Confirmed_MAE": 1.74,
        "Relative_MAE_Improvement": 0.0057,
        "Confirmed_Win_Share": 0.525,
        "Confirmed_Loss_Share": 0.475,
        "Preconfirm_Bias": 0.10,
        "Confirmed_Bias": 0.11,
        "Mean_Absolute_Projection_Delta": 0.09,
        "Reason": "Frozen source gate is supported at minimum evaluation volume.",
        "Manual_Review_Ready": False,
        "Recommended_Action": "KEEP_AND_MONITOR",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "Validation_Version": "lineup-k-walkforward-v2-lineage-safe-report-only",
    }])


def test_ten_day_status_transition_has_snapshot_and_manual_queue_trigger() -> None:
    snapshot = build_review_snapshot(_segments())
    review = build_review_summary(_gate(), snapshot).iloc[0]
    assert review["Review_Status"] == "MINIMUM_EVALUATION_REVIEW_REQUIRED"
    assert bool(review["Human_Review_Required"]) is True
    assert bool(review["Source_Manual_Review_Ready"]) is False

    digest = pd.DataFrame([{
        "Refresh_At_UTC": REFRESH,
        "Lane": "Confirmed Lineup",
        "Category": "LINEUP",
        "Previous_Status": "LEARNING",
        "Status": "SUPPORTED",
        "Status_Changed": True,
        "Readiness_Changed": False,
        "Evidence_Direction": "relative_mae=+0.57%; win_share=52.5%",
        "Current_Starts": 160,
        "Required_Starts": 30,
        "Starts_Remaining": 0,
        "Current_Days": 10,
        "Required_Days": 10,
        "Days_Remaining": 0,
        "Breadth_Label": "OPPONENTS",
        "Current_Breadth": 30,
        "Required_Breadth": 8,
        "Breadth_Remaining": 0,
        "Secondary_Progress": "authentic_pairs=180",
        "Ready_For_Manual_Review": False,
        "Recommended_Action": "KEEP_AND_MONITOR",
        "Source_Reason": "Frozen source gate is supported at minimum evaluation volume.",
        "Change_Summary": "Status:LEARNING->SUPPORTED; Current_Days:9->10",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "No_Auto_Promotion": True,
        "Control_Violation": False,
        "Source_Version": "lineup-k-walkforward-v2-lineage-safe-report-only",
    }])
    history = pd.DataFrame([
        {
            "Observed_At_UTC": "2026-08-24T14:00:00+00:00",
            "Event_Type": "BASELINE_CAPTURE",
            "Lane": "Confirmed Lineup",
            "Category": "LINEUP",
            "Status": "LEARNING",
            "Current_Starts": 150,
            "Current_Days": 9,
            "Current_Breadth": 30,
            "Ready_For_Manual_Review": False,
            "Recommended_Action": "KEEP_LEARNING",
        },
        {
            "Observed_At_UTC": REFRESH,
            "Event_Type": "EVIDENCE_CHANGE",
            "Lane": "Confirmed Lineup",
            "Category": "LINEUP",
            "Status": "SUPPORTED",
            "Current_Starts": 160,
            "Current_Days": 10,
            "Current_Breadth": 30,
            "Ready_For_Manual_Review": False,
            "Recommended_Action": "KEEP_AND_MONITOR",
        },
    ])
    center = pd.DataFrame([{
        "Lane": "Confirmed Lineup",
        "Source_Path": "data/lineup_k_walkforward_gate.csv",
    }])

    packet = build_manual_review_packet(digest, history, center, REFRESH)
    assert len(packet) == 1
    row = packet.iloc[0]
    assert row["Review_Trigger"] == "STATUS_TRANSITION"
    assert row["Previous_Status"] == "LEARNING"
    assert row["Status"] == "SUPPORTED"
    assert bool(row["Ready_For_Manual_Review"]) is False
    assert bool(row["Human_Review_Required"]) is True
    assert bool(row["Automatic_Decision_Allowed"]) is False
    assert row["Production_Authority"] == "NONE"
