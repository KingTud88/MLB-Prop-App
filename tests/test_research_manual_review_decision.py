from __future__ import annotations

import pandas as pd
import pytest

from training.research_manual_review_decision import (
    ALLOWED_REVIEW_STATUSES,
    VERSION,
    apply_manual_review_decision,
)
from training.research_manual_review_queue import (
    AUTOMATIC_DECISION_ALLOWED,
    DEFAULT_REVIEW_STATUS,
    NO_AUTO_PROMOTION,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    append_review_queue,
)

REVIEWED_AT = "2026-08-19T13:51:31+00:00"


def _packet(case_refresh: str, lane: str = "Calibration Shadow") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Refresh_At_UTC": case_refresh,
                "Lane": lane,
                "Category": "CALIBRATION",
                "Review_Trigger": "MULTICELL_MATURITY_TRANSITION",
                "Previous_Status": "FAIL",
                "Status": "FAIL",
                "Previous_Ready_For_Manual_Review": False,
                "Ready_For_Manual_Review": True,
                "Previous_Evidence_Direction": "milestones_pass=0/8; milestones_fail=8/8",
                "Evidence_Direction": "milestones_pass=0/8; milestones_fail=8/8",
                "Current_Starts": 138,
                "Required_Starts": 30,
                "Starts_Remaining": 0,
                "Breadth_Label": "MILESTONE_CELLS",
                "Current_Breadth": 8,
                "Required_Breadth": 8,
                "Breadth_Remaining": 0,
                "Secondary_Progress": "mature_cells=8/8",
                "Recommended_Action": "MANUAL_REVIEW_MULTICELL_CALIBRATION_EVIDENCE_ONLY",
                "Source_Path": "data/calibration_shadow_gate.csv",
                "Source_Version": "calibration-shadow-gate-v1",
                "Source_Reason": "All frozen calibration cells meet their existing sample requirement.",
                "Change_Summary": "Multicell_Maturity:False->True",
                "Report_Only": True,
                "Production_Authority": "NONE",
                "No_Auto_Promotion": True,
                "Automatic_Decision_Allowed": False,
                "Human_Review_Required": True,
                "Control_Violation": False,
                "Packet_Version": "research-manual-review-packet-v1-report-only",
            }
        ]
    )


def _queue() -> pd.DataFrame:
    return append_review_queue(_packet("2026-08-19T13:46:03+00:00"), queued_at_utc="2026-08-19T13:46:03+00:00")


def test_closes_one_pending_case_and_recomputes_summary() -> None:
    queue = _queue()
    case_id = str(queue.iloc[0]["Review_Case_ID"])
    decided, summary = apply_manual_review_decision(
        queue,
        case_id=case_id,
        reviewer="owner",
        notes="Keep report-only; no promotion; preserve the negative calibration result.",
        reviewed_at_utc=REVIEWED_AT,
    )
    row = decided.iloc[0]
    assert row["Review_Status"] == "CLOSED_BY_HUMAN"
    assert row["Reviewed_At_UTC"] == REVIEWED_AT
    assert row["Reviewer"] == "owner"
    assert "no promotion" in row["Review_Notes"]
    assert row["Production_Authority"] == "NONE"
    assert bool(row["Automatic_Decision_Allowed"]) is False

    srow = summary.iloc[0]
    assert srow["Queue_Status"] == "NO_PENDING_REVIEW"
    assert int(srow["Total_Cases"]) == 1
    assert int(srow["Pending_Cases"]) == 0
    assert int(srow["Non_Pending_Cases"]) == 1


def test_non_target_case_is_preserved_verbatim() -> None:
    first = _queue()
    second = append_review_queue(
        _packet("2026-08-20T13:46:03+00:00", lane="Starter Role Live Shadow"),
        first,
        queued_at_utc="2026-08-20T13:46:03+00:00",
    )
    target_id = str(second.iloc[0]["Review_Case_ID"])
    untouched_before = second.iloc[1].copy()
    decided, _ = apply_manual_review_decision(
        second,
        case_id=target_id,
        reviewer="owner",
        notes="Reviewed calibration evidence only.",
        reviewed_at_utc=REVIEWED_AT,
    )
    assert decided.iloc[1].equals(untouched_before)
    assert decided.iloc[1]["Review_Status"] == DEFAULT_REVIEW_STATUS


def test_missing_or_duplicate_case_id_is_rejected() -> None:
    queue = _queue()
    with pytest.raises(ValueError, match="exactly one review case"):
        apply_manual_review_decision(
            queue,
            case_id="missing",
            reviewer="owner",
            notes="not found",
            reviewed_at_utc=REVIEWED_AT,
        )

    duplicate = pd.concat([queue, queue], ignore_index=True)
    case_id = str(queue.iloc[0]["Review_Case_ID"])
    with pytest.raises(ValueError, match="exactly one review case"):
        apply_manual_review_decision(
            duplicate,
            case_id=case_id,
            reviewer="owner",
            notes="duplicate",
            reviewed_at_utc=REVIEWED_AT,
        )


def test_already_closed_case_cannot_be_decided_again() -> None:
    queue = _queue()
    queue.loc[0, "Review_Status"] = "CLOSED_BY_HUMAN"
    case_id = str(queue.iloc[0]["Review_Case_ID"])
    with pytest.raises(ValueError, match="pending review case"):
        apply_manual_review_decision(
            queue,
            case_id=case_id,
            reviewer="owner",
            notes="second decision",
            reviewed_at_utc=REVIEWED_AT,
        )


def test_control_or_authority_violation_fails_closed() -> None:
    for column, value, message in (
        ("Control_Violation", True, "control-violation"),
        ("Report_Only", False, "Report_Only"),
        ("Production_Authority", "MODEL", "Production_Authority"),
        ("No_Auto_Promotion", False, "No_Auto_Promotion"),
        ("Automatic_Decision_Allowed", True, "automatic decisions"),
    ):
        queue = _queue()
        queue.loc[0, column] = value
        case_id = str(queue.iloc[0]["Review_Case_ID"])
        with pytest.raises(ValueError, match=message):
            apply_manual_review_decision(
                queue,
                case_id=case_id,
                reviewer="owner",
                notes="blocked",
                reviewed_at_utc=REVIEWED_AT,
            )


def test_review_inputs_and_status_are_explicit() -> None:
    queue = _queue()
    case_id = str(queue.iloc[0]["Review_Case_ID"])
    for reviewer, notes, reviewed_at, message in (
        ("", "notes", REVIEWED_AT, "reviewer is required"),
        ("owner", "", REVIEWED_AT, "review notes are required"),
        ("owner", "notes", "", "reviewed_at_utc is required"),
    ):
        with pytest.raises(ValueError, match=message):
            apply_manual_review_decision(
                queue,
                case_id=case_id,
                reviewer=reviewer,
                notes=notes,
                reviewed_at_utc=reviewed_at,
            )

    with pytest.raises(ValueError, match="unsupported manual review status"):
        apply_manual_review_decision(
            queue,
            case_id=case_id,
            reviewer="owner",
            notes="notes",
            reviewed_at_utc=REVIEWED_AT,
            review_status="APPROVED",
        )


def test_manual_only_contract_is_frozen() -> None:
    assert VERSION == "research-manual-review-decision-v1-manual-only"
    assert ALLOWED_REVIEW_STATUSES == ("CLOSED_BY_HUMAN",)
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert NO_AUTO_PROMOTION is True
    assert AUTOMATIC_DECISION_ALLOWED is False
