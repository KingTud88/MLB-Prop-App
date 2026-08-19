from __future__ import annotations

import pandas as pd

from training.research_manual_review_packet import (
    AUTOMATIC_DECISION_ALLOWED,
    NO_AUTO_PROMOTION,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    VERSION,
    build_manual_review_packet,
    build_packet_summary,
)

REFRESH = "2026-08-18T14:00:00+00:00"


def _digest_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "Refresh_At_UTC": REFRESH,
        "Lane": "Confirmed Lineup",
        "Category": "LINEUP",
        "Previous_Status": "LEARNING",
        "Status": "READY_FOR_MANUAL_RESEARCH_REVIEW",
        "Status_Changed": True,
        "Evidence_Direction_Changed": False,
        "Progress_Changed": True,
        "Readiness_Changed": True,
        "Action_Changed": True,
        "Source_Version_Changed": False,
        "Evidence_Direction": "relative_mae=+0.60%; win_share=52.5%",
        "Current_Starts": 180,
        "Required_Starts": 30,
        "Starts_Remaining": 0,
        "Current_Days": 10,
        "Required_Days": 10,
        "Days_Remaining": 0,
        "Breadth_Label": "OPPONENTS",
        "Current_Breadth": 30,
        "Required_Breadth": 8,
        "Breadth_Remaining": 0,
        "Secondary_Progress": "authentic_pairs=205",
        "Ready_For_Manual_Review": True,
        "Recommended_Action": "MANUAL_RESEARCH_REVIEW",
        "Source_Reason": "Frozen gate is mature for manual review.",
        "Change_Summary": "Status:LEARNING->READY_FOR_MANUAL_RESEARCH_REVIEW; Current_Starts:120->180; Current_Days:5->10; Ready_For_Manual_Review:False->True; Recommended_Action:KEEP_LEARNING->MANUAL_RESEARCH_REVIEW",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "No_Auto_Promotion": True,
        "Control_Violation": False,
        "Source_Version": "lineup-k-walkforward-v2-lineage-safe-report-only",
    }
    row.update(overrides)
    return row


def _history() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Observed_At_UTC": "2026-08-17T14:00:00+00:00",
            "Event_Type": "BASELINE_CAPTURE",
            "Lane": "Confirmed Lineup",
            "Category": "LINEUP",
            "Status": "LEARNING",
            "Evidence_Direction": "relative_mae=+0.49%; win_share=51.7%",
            "Current_Starts": 120,
            "Required_Starts": 30,
            "Current_Days": 5,
            "Required_Days": 10,
            "Current_Breadth": 30,
            "Required_Breadth": 8,
            "Secondary_Progress": "authentic_pairs=148",
            "Ready_For_Manual_Review": False,
            "Recommended_Action": "KEEP_LEARNING",
            "Report_Only": True,
            "Production_Authority": "NONE",
            "No_Auto_Promotion": True,
            "Source_Version": "lineup-k-walkforward-v2-lineage-safe-report-only",
        },
        {
            "Observed_At_UTC": REFRESH,
            "Event_Type": "EVIDENCE_CHANGE",
            "Lane": "Confirmed Lineup",
            "Category": "LINEUP",
            "Previous_Status": "LEARNING",
            "Status": "READY_FOR_MANUAL_RESEARCH_REVIEW",
            "Evidence_Direction": "relative_mae=+0.60%; win_share=52.5%",
            "Current_Starts": 180,
            "Required_Starts": 30,
            "Current_Days": 10,
            "Required_Days": 10,
            "Current_Breadth": 30,
            "Required_Breadth": 8,
            "Secondary_Progress": "authentic_pairs=205",
            "Ready_For_Manual_Review": True,
            "Recommended_Action": "MANUAL_RESEARCH_REVIEW",
            "Report_Only": True,
            "Production_Authority": "NONE",
            "No_Auto_Promotion": True,
            "Source_Version": "lineup-k-walkforward-v2-lineage-safe-report-only",
        },
    ])


def _center() -> pd.DataFrame:
    return pd.DataFrame([{
        "Lane": "Confirmed Lineup",
        "Source_Path": "data/lineup_k_walkforward_gate.csv",
    }])


def test_no_digest_changes_produce_no_review_trigger() -> None:
    packet = build_manual_review_packet(pd.DataFrame(), _history(), _center(), REFRESH)
    summary = build_packet_summary(packet, pd.DataFrame(), REFRESH)
    assert packet.empty
    assert summary.iloc[0]["Packet_Status"] == "NO_REVIEW_TRIGGER"
    assert int(summary.iloc[0]["Triggered_Lanes"]) == 0


def test_progress_only_change_below_primary_milestone_is_excluded() -> None:
    digest = pd.DataFrame([_digest_row(
        Status="LEARNING",
        Status_Changed=False,
        Readiness_Changed=False,
        Action_Changed=False,
        Ready_For_Manual_Review=False,
        Current_Starts=121,
        Current_Days=6,
        Recommended_Action="KEEP_LEARNING",
        Change_Summary="Current_Starts:120->121; Current_Days:5->6",
    )])
    packet = build_manual_review_packet(digest, _history(), _center(), REFRESH)
    assert packet.empty


def test_primary_milestone_crossing_triggers_review_without_status_change() -> None:
    history = _history()
    history.loc[0, "Lane"] = "Opponent Asymmetric Challenger"
    history.loc[0, "Category"] = "OPPONENT"
    history.loc[0, "Status"] = "INCONCLUSIVE"
    history.loc[0, "Current_Starts"] = 59
    history.loc[0, "Required_Starts"] = 60
    history.loc[0, "Current_Days"] = 9
    history.loc[0, "Required_Days"] = 10
    history.loc[0, "Current_Breadth"] = 15
    history.loc[0, "Required_Breadth"] = 15
    history.loc[0, "Recommended_Action"] = "KEEP_COMPOSITE_FROZEN_AND_LEARN"
    history.loc[1, "Lane"] = "Opponent Asymmetric Challenger"
    center = pd.DataFrame([{
        "Lane": "Opponent Asymmetric Challenger",
        "Source_Path": "data/opponent_matchup_asymmetric_response_shadow_gate.csv",
    }])
    digest = pd.DataFrame([_digest_row(
        Lane="Opponent Asymmetric Challenger",
        Category="OPPONENT",
        Previous_Status="INCONCLUSIVE",
        Status="INCONCLUSIVE",
        Status_Changed=False,
        Readiness_Changed=False,
        Action_Changed=False,
        Ready_For_Manual_Review=False,
        Current_Starts=60,
        Required_Starts=60,
        Starts_Remaining=0,
        Current_Days=10,
        Required_Days=10,
        Days_Remaining=0,
        Current_Breadth=15,
        Required_Breadth=15,
        Breadth_Remaining=0,
        Recommended_Action="KEEP_COMPOSITE_FROZEN_AND_LEARN",
        Change_Summary="Current_Starts:59->60; Current_Days:9->10",
    )])
    packet = build_manual_review_packet(digest, history, center, REFRESH)
    assert len(packet) == 1
    row = packet.iloc[0]
    assert row["Review_Trigger"] == "PRIMARY_MILESTONE_TRANSITION"
    assert row["Previous_Status"] == "INCONCLUSIVE"
    assert row["Status"] == "INCONCLUSIVE"
    assert bool(row["Human_Review_Required"]) is True
    assert bool(row["Automatic_Decision_Allowed"]) is False
    assert row["Production_Authority"] == "NONE"


def test_action_transition_triggers_review_without_status_or_readiness_change() -> None:
    digest = pd.DataFrame([_digest_row(
        Status="INCONCLUSIVE",
        Status_Changed=False,
        Readiness_Changed=False,
        Action_Changed=True,
        Ready_For_Manual_Review=False,
        Current_Starts=27,
        Required_Starts=60,
        Current_Days=1,
        Required_Days=10,
        Current_Breadth=26,
        Required_Breadth=15,
        Recommended_Action="KEEP_COMPOSITE_UNCHANGED_PENDING_MANUAL_REVIEW",
        Change_Summary="Recommended_Action:KEEP_COMPOSITE_FROZEN_AND_LEARN->KEEP_COMPOSITE_UNCHANGED_PENDING_MANUAL_REVIEW",
    )])
    packet = build_manual_review_packet(digest, _history(), _center(), REFRESH)
    assert len(packet) == 1
    assert packet.iloc[0]["Review_Trigger"] == "ACTION_TRANSITION"


def test_single_dimension_primary_milestone_is_supported() -> None:
    history = _history()
    history.loc[0, "Lane"] = "Top Plays Accountability"
    history.loc[0, "Category"] = "EXECUTION"
    history.loc[0, "Status"] = "LEARNING"
    history.loc[0, "Current_Starts"] = 19
    history.loc[0, "Required_Starts"] = 20
    history.loc[0, "Current_Days"] = None
    history.loc[0, "Required_Days"] = None
    history.loc[0, "Current_Breadth"] = None
    history.loc[0, "Required_Breadth"] = None
    history.loc[0, "Recommended_Action"] = "KEEP_TOP_PLAYS_ACCOUNTABILITY_LEARNING"
    history.loc[1, "Lane"] = "Top Plays Accountability"
    center = pd.DataFrame([{
        "Lane": "Top Plays Accountability",
        "Source_Path": "data/top_plays_accountability_summary.csv",
    }])
    digest = pd.DataFrame([_digest_row(
        Lane="Top Plays Accountability",
        Category="EXECUTION",
        Status="LEARNING",
        Status_Changed=False,
        Readiness_Changed=False,
        Action_Changed=False,
        Ready_For_Manual_Review=False,
        Current_Starts=20,
        Required_Starts=20,
        Starts_Remaining=0,
        Current_Days=None,
        Required_Days=None,
        Days_Remaining=None,
        Current_Breadth=None,
        Required_Breadth=None,
        Breadth_Remaining=None,
        Recommended_Action="KEEP_TOP_PLAYS_ACCOUNTABILITY_LEARNING",
        Change_Summary="Current_Starts:19->20",
    )])
    packet = build_manual_review_packet(digest, history, center, REFRESH)
    assert len(packet) == 1
    assert packet.iloc[0]["Review_Trigger"] == "PRIMARY_MILESTONE_TRANSITION"


def test_status_and_readiness_transition_builds_before_after_packet() -> None:
    digest = pd.DataFrame([_digest_row()])
    packet = build_manual_review_packet(digest, _history(), _center(), REFRESH)
    assert len(packet) == 1
    row = packet.iloc[0]
    assert row["Review_Trigger"] == "STATUS_AND_READINESS_TRANSITION"
    assert row["Previous_Status"] == "LEARNING"
    assert row["Status"] == "READY_FOR_MANUAL_RESEARCH_REVIEW"
    assert bool(row["Previous_Ready_For_Manual_Review"]) is False
    assert bool(row["Ready_For_Manual_Review"]) is True
    assert int(row["Previous_Starts"]) == 120
    assert int(row["Current_Starts"]) == 180
    assert int(row["Previous_Days"]) == 5
    assert int(row["Current_Days"]) == 10
    assert row["Source_Path"] == "data/lineup_k_walkforward_gate.csv"
    assert row["Previous_Recommended_Action"] == "KEEP_LEARNING"
    assert row["Recommended_Action"] == "MANUAL_RESEARCH_REVIEW"
    assert bool(row["Automatic_Decision_Allowed"]) is False
    assert bool(row["Human_Review_Required"]) is True

    summary = build_packet_summary(packet, digest, REFRESH)
    srow = summary.iloc[0]
    assert srow["Packet_Status"] == "MANUAL_REVIEW_PACKET_READY"
    assert int(srow["Triggered_Lanes"]) == 1
    assert int(srow["Status_Transition_Lanes"]) == 1
    assert int(srow["Readiness_Transition_Lanes"]) == 1
    assert int(srow["Newly_Review_Ready_Lanes"]) == 1


def test_status_only_transition_is_review_trigger_even_if_not_ready() -> None:
    digest = pd.DataFrame([_digest_row(
        Status="FAIL",
        Status_Changed=True,
        Readiness_Changed=False,
        Ready_For_Manual_Review=False,
        Change_Summary="Status:LEARNING->FAIL",
    )])
    packet = build_manual_review_packet(digest, _history(), _center(), REFRESH)
    assert len(packet) == 1
    assert packet.iloc[0]["Review_Trigger"] == "STATUS_TRANSITION"
    summary = build_packet_summary(packet, digest, REFRESH)
    assert int(summary.iloc[0]["Newly_Review_Ready_Lanes"]) == 0


def test_control_violation_overrides_packet_status() -> None:
    digest = pd.DataFrame([_digest_row(
        Production_Authority="MODEL",
        Control_Violation=True,
    )])
    packet = build_manual_review_packet(digest, _history(), _center(), REFRESH)
    assert bool(packet.iloc[0]["Control_Violation"]) is True
    summary = build_packet_summary(packet, digest, REFRESH)
    assert summary.iloc[0]["Packet_Status"] == "CONTROL_VIOLATION"
    assert int(summary.iloc[0]["Control_Violation_Lanes"]) == 1


def test_report_only_constants_are_frozen() -> None:
    assert VERSION == "research-manual-review-packet-v1-report-only"
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert NO_AUTO_PROMOTION is True
    assert AUTOMATIC_DECISION_ALLOWED is False
