from __future__ import annotations

import pandas as pd

from training.research_manual_review_queue import (
    AUTOMATIC_DECISION_ALLOWED,
    DEFAULT_REVIEW_STATUS,
    NO_AUTO_PROMOTION,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    VERSION,
    append_review_queue,
    build_queue_summary,
)


def _packet(refresh: str = "2026-08-18T14:00:00+00:00", lane: str = "Confirmed Lineup") -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Refresh_At_UTC": refresh,
            "Lane": lane,
            "Category": "LINEUP",
            "Review_Trigger": "STATUS_AND_READINESS_TRANSITION",
            "Previous_Status": "LEARNING",
            "Status": "READY_FOR_MANUAL_RESEARCH_REVIEW",
            "Previous_Ready_For_Manual_Review": False,
            "Ready_For_Manual_Review": True,
            "Previous_Evidence_Direction": "old",
            "Evidence_Direction": "new",
            "Previous_Starts": 120,
            "Current_Starts": 180,
            "Required_Starts": 30,
            "Starts_Remaining": 0,
            "Previous_Days": 5,
            "Current_Days": 10,
            "Required_Days": 10,
            "Days_Remaining": 0,
            "Breadth_Label": "OPPONENTS",
            "Previous_Breadth": 30,
            "Current_Breadth": 30,
            "Required_Breadth": 8,
            "Breadth_Remaining": 0,
            "Previous_Secondary_Progress": "authentic_pairs=148",
            "Secondary_Progress": "authentic_pairs=205",
            "Previous_Recommended_Action": "KEEP_LEARNING",
            "Recommended_Action": "MANUAL_RESEARCH_REVIEW",
            "Source_Path": "data/lineup_k_walkforward_gate.csv",
            "Source_Version": "lineup-k-walkforward-v2-lineage-safe-report-only",
            "Source_Reason": "Frozen gate is mature for manual review.",
            "Change_Summary": "Status:LEARNING->READY_FOR_MANUAL_RESEARCH_REVIEW; Ready_For_Manual_Review:False->True",
            "Report_Only": True,
            "Production_Authority": "NONE",
            "No_Auto_Promotion": True,
            "Automatic_Decision_Allowed": False,
            "Human_Review_Required": True,
            "Control_Violation": False,
            "Packet_Version": "research-manual-review-packet-v1-report-only",
        }
    ])


def test_packet_appends_pending_case() -> None:
    queue = append_review_queue(_packet(), queued_at_utc="2026-08-18T14:01:00+00:00")
    assert len(queue) == 1
    row = queue.iloc[0]
    assert row["Review_Status"] == DEFAULT_REVIEW_STATUS
    assert row["Reviewer"] == ""
    assert row["Review_Notes"] == ""
    assert row["Lane"] == "Confirmed Lineup"
    assert bool(row["Automatic_Decision_Allowed"]) is False


def test_same_packet_is_idempotent() -> None:
    first = append_review_queue(_packet(), queued_at_utc="2026-08-18T14:01:00+00:00")
    second = append_review_queue(_packet(), first, queued_at_utc="2026-08-18T14:02:00+00:00")
    assert len(second) == 1
    assert second.iloc[0]["Review_Case_ID"] == first.iloc[0]["Review_Case_ID"]


def test_no_change_packet_does_not_erase_pending_case() -> None:
    first = append_review_queue(_packet(), queued_at_utc="2026-08-18T14:01:00+00:00")
    second = append_review_queue(pd.DataFrame(), first, queued_at_utc="2026-08-18T15:00:00+00:00")
    assert len(second) == 1
    assert second.iloc[0]["Review_Status"] == DEFAULT_REVIEW_STATUS


def test_manual_review_fields_are_preserved_verbatim() -> None:
    first = append_review_queue(_packet(), queued_at_utc="2026-08-18T14:01:00+00:00")
    first.loc[0, "Review_Status"] = "CLOSED_BY_HUMAN"
    first.loc[0, "Reviewed_At_UTC"] = "2026-08-18T14:30:00+00:00"
    first.loc[0, "Reviewer"] = "owner"
    first.loc[0, "Review_Notes"] = "Keep report-only; collect more evidence."
    second = append_review_queue(pd.DataFrame(), first, queued_at_utc="2026-08-18T15:00:00+00:00")
    row = second.iloc[0]
    assert row["Review_Status"] == "CLOSED_BY_HUMAN"
    assert row["Reviewed_At_UTC"] == "2026-08-18T14:30:00+00:00"
    assert row["Reviewer"] == "owner"
    assert row["Review_Notes"] == "Keep report-only; collect more evidence."


def test_later_transition_for_same_lane_creates_distinct_case() -> None:
    first = append_review_queue(_packet(), queued_at_utc="2026-08-18T14:01:00+00:00")
    later = _packet(refresh="2026-08-20T14:00:00+00:00")
    later.loc[0, "Previous_Status"] = "READY_FOR_MANUAL_RESEARCH_REVIEW"
    later.loc[0, "Status"] = "LEARNING"
    later.loc[0, "Change_Summary"] = "Status:READY_FOR_MANUAL_RESEARCH_REVIEW->LEARNING"
    second = append_review_queue(later, first, queued_at_utc="2026-08-20T14:01:00+00:00")
    assert len(second) == 2
    assert second["Review_Case_ID"].nunique() == 2


def test_summary_reports_pending_and_control_violation_without_deciding() -> None:
    queue = append_review_queue(_packet(), queued_at_utc="2026-08-18T14:01:00+00:00")
    summary = build_queue_summary(queue, "2026-08-18T14:02:00+00:00")
    assert summary.iloc[0]["Queue_Status"] == "PENDING_MANUAL_REVIEW"
    assert int(summary.iloc[0]["Pending_Cases"]) == 1
    assert int(summary.iloc[0]["Pending_Lanes"]) == 1
    assert bool(summary.iloc[0]["Automatic_Decision_Allowed"]) is False

    queue.loc[0, "Control_Violation"] = True
    violation_summary = build_queue_summary(queue, "2026-08-18T14:03:00+00:00")
    assert violation_summary.iloc[0]["Queue_Status"] == "CONTROL_VIOLATION"
    assert int(violation_summary.iloc[0]["Control_Violation_Cases"]) == 1


def test_report_only_constants_are_frozen() -> None:
    assert VERSION == "research-manual-review-queue-v1-report-only"
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert NO_AUTO_PROMOTION is True
    assert AUTOMATIC_DECISION_ALLOWED is False
    assert DEFAULT_REVIEW_STATUS == "PENDING_MANUAL_REVIEW"
