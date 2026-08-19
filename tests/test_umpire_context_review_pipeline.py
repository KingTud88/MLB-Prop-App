from __future__ import annotations

import pandas as pd

from training.research_manual_review_packet import build_manual_review_packet
from training.umpire_context_review_snapshot import build_review_snapshot, build_review_summary

REFRESH = "2026-08-25T14:00:00+00:00"


def _segments() -> pd.DataFrame:
    return pd.DataFrame([{
        "Dimension": "OVERALL",
        "Segment": "ALL LIVE UMPIRE CANDIDATES",
        "Rows": 120,
        "Authentic_Pregame_Candidates": 110,
        "OOS_Eligible_Starts": 104,
        "Observed_Days": 10,
        "Distinct_Umpires": 46,
        "Base_MAE": 1.75,
        "UmpireCandidate_MAE": 1.77,
        "Relative_MAE_Improvement": -0.0084,
        "Candidate_Win_Share": 0.462,
        "Candidate_Loss_Share": 0.538,
        "Base_Bias": 0.22,
        "UmpireCandidate_Bias": 0.224,
        "Mean_Absolute_Factor_Delta": 0.031,
        "Evidence": "CAUTION",
        "Reason": "Minimum frozen evaluation gate is mature.",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "Validation_Version": "umpire-k-live-validation-v1-lineage-safe-report-only",
    }])


def _gate() -> pd.DataFrame:
    return pd.DataFrame([{
        "Evidence_Status": "CAUTION",
        "Captured_Candidates": 139,
        "Authentic_Pregame_Candidates": 104,
        "OOS_Eligible_Starts": 104,
        "Observed_Days": 10,
        "Distinct_Umpires": 46,
        "Base_MAE": 1.75,
        "UmpireCandidate_MAE": 1.77,
        "Relative_MAE_Improvement": -0.0084,
        "Candidate_Win_Share": 0.462,
        "Candidate_Loss_Share": 0.538,
        "Base_Bias": 0.22,
        "UmpireCandidate_Bias": 0.224,
        "Mean_Absolute_Factor_Delta": 0.031,
        "Reason": "Frozen source gate is caution at minimum evaluation volume.",
        "Manual_Review_Ready": False,
        "Recommended_Action": "MANUAL_REVIEW",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "Validation_Version": "umpire-k-live-validation-v1-lineage-safe-report-only",
    }])


def test_ten_day_status_transition_has_snapshot_and_manual_queue_trigger() -> None:
    snapshot = build_review_snapshot(_segments())
    review = build_review_summary(_gate(), snapshot).iloc[0]
    assert review["Review_Status"] == "MINIMUM_EVALUATION_REVIEW_REQUIRED"
    assert bool(review["Human_Review_Required"]) is True
    assert bool(review["Source_Manual_Review_Ready"]) is False

    digest = pd.DataFrame([{
        "Refresh_At_UTC": REFRESH,
        "Lane": "Umpire Context",
        "Category": "CONTEXT",
        "Previous_Status": "LEARNING",
        "Status": "CAUTION",
        "Status_Changed": True,
        "Readiness_Changed": False,
        "Evidence_Direction": "relative_mae=-0.84%; win_share=46.2%",
        "Current_Starts": 104,
        "Required_Starts": 30,
        "Starts_Remaining": 0,
        "Current_Days": 10,
        "Required_Days": 10,
        "Days_Remaining": 0,
        "Breadth_Label": "UMPIRES",
        "Current_Breadth": 46,
        "Required_Breadth": 8,
        "Breadth_Remaining": 0,
        "Secondary_Progress": "",
        "Ready_For_Manual_Review": False,
        "Recommended_Action": "MANUAL_REVIEW",
        "Source_Reason": "Frozen source gate is caution at minimum evaluation volume.",
        "Change_Summary": "Status:LEARNING->CAUTION; Current_Days:9->10",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "No_Auto_Promotion": True,
        "Control_Violation": False,
        "Source_Version": "umpire-k-live-validation-v1-lineage-safe-report-only",
    }])
    history = pd.DataFrame([
        {
            "Observed_At_UTC": "2026-08-24T14:00:00+00:00",
            "Event_Type": "BASELINE_CAPTURE",
            "Lane": "Umpire Context",
            "Category": "CONTEXT",
            "Status": "LEARNING",
            "Current_Starts": 100,
            "Current_Days": 9,
            "Current_Breadth": 44,
            "Ready_For_Manual_Review": False,
            "Recommended_Action": "KEEP_LEARNING",
        },
        {
            "Observed_At_UTC": REFRESH,
            "Event_Type": "EVIDENCE_CHANGE",
            "Lane": "Umpire Context",
            "Category": "CONTEXT",
            "Status": "CAUTION",
            "Current_Starts": 104,
            "Current_Days": 10,
            "Current_Breadth": 46,
            "Ready_For_Manual_Review": False,
            "Recommended_Action": "MANUAL_REVIEW",
        },
    ])
    center = pd.DataFrame([{
        "Lane": "Umpire Context",
        "Source_Path": "data/umpire_k_live_validation_gate.csv",
    }])

    packet = build_manual_review_packet(digest, history, center, REFRESH)
    assert len(packet) == 1
    row = packet.iloc[0]
    assert row["Review_Trigger"] == "STATUS_TRANSITION"
    assert row["Previous_Status"] == "LEARNING"
    assert row["Status"] == "CAUTION"
    assert bool(row["Ready_For_Manual_Review"]) is False
    assert bool(row["Human_Review_Required"]) is True
    assert bool(row["Automatic_Decision_Allowed"]) is False
    assert row["Production_Authority"] == "NONE"
