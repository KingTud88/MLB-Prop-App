from __future__ import annotations

import pandas as pd

from training.calibration_shadow_gate import (
    GATE_VERSION as CALIBRATION_GATE_VERSION,
    MILESTONES as CALIBRATION_MILESTONES,
    MIN_OOS_STARTS as CALIBRATION_MIN_OOS_STARTS,
)
from training.live_role_shadow_gate import (
    GATE_VERSION as ROLE_GATE_VERSION,
    MIN_RESOLVED_STARTS as ROLE_MIN_RESOLVED_STARTS,
    REQUIRED_METRICS,
    REQUIRED_ROLES,
)
from training.research_manual_review_packet import build_packet_summary
from training.research_manual_review_queue import append_review_queue, build_queue_summary
from training.research_multicell_review_injector import (
    AUTOMATIC_DECISION_ALLOWED,
    NO_AUTO_PROMOTION,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    REVIEW_TRIGGER,
    VERSION,
    inject_multicell_reviews,
)

REFRESH = "2026-08-19T14:00:00+00:00"


def _calibration(*, complete: bool = True, starts: int | None = None) -> pd.DataFrame:
    threshold = CALIBRATION_MIN_OOS_STARTS if starts is None else starts
    milestones = list(CALIBRATION_MILESTONES)
    if not complete:
        milestones = milestones[:-1]
    return pd.DataFrame(
        [
            {
                "Milestone": milestone,
                "OOS_Starts": threshold,
                "Relative_Brier_Improvement": -0.01,
                "Baseline_Calibration_Gap": 0.04,
                "Candidate_Calibration_Gap": 0.05,
                "Candidate_Win_Share": 0.4,
                "Promotion_Gate_Status": "FAIL",
                "Reasons": "brier|calibration_gap",
                "Gate_Version": CALIBRATION_GATE_VERSION,
            }
            for milestone in milestones
        ]
    )


def _role(*, complete: bool = True, starts: int | None = None) -> pd.DataFrame:
    threshold = ROLE_MIN_RESOLVED_STARTS if starts is None else starts
    rows = [
        {
            "Role": role,
            "Metric": metric,
            "Resolved_Starts": threshold,
            "Relative_MAE": -0.02,
            "Candidate_Win_Share": 0.4,
            "Baseline_Bias": 1.0,
            "Candidate_Bias": 1.2,
            "Live_Gate_Status": "FAIL",
            "Reasons": "mae|win_share|bias",
            "Gate_Version": ROLE_GATE_VERSION,
        }
        for role in REQUIRED_ROLES
        for metric in REQUIRED_METRICS
    ]
    if not complete:
        rows = rows[:-1]
    return pd.DataFrame(rows)


def test_calibration_requires_every_frozen_milestone_cell() -> None:
    packet = inject_multicell_reviews(
        pd.DataFrame(),
        pd.DataFrame(),
        _calibration(complete=False),
        pd.DataFrame(),
        REFRESH,
    )
    assert packet.empty


def test_calibration_full_maturity_injects_one_manual_review_case() -> None:
    packet = inject_multicell_reviews(
        pd.DataFrame(),
        pd.DataFrame(),
        _calibration(),
        pd.DataFrame(),
        REFRESH,
    )
    assert len(packet) == 1
    row = packet.iloc[0]
    assert row["Lane"] == "Calibration Shadow"
    assert row["Review_Trigger"] == REVIEW_TRIGGER
    assert row["Status"] == "FAIL"
    assert int(row["Current_Starts"]) == CALIBRATION_MIN_OOS_STARTS
    assert int(row["Required_Starts"]) == CALIBRATION_MIN_OOS_STARTS
    assert int(row["Current_Breadth"]) == len(CALIBRATION_MILESTONES)
    assert int(row["Required_Breadth"]) == len(CALIBRATION_MILESTONES)
    assert bool(row["Ready_For_Manual_Review"]) is True
    assert bool(row["Human_Review_Required"]) is True
    assert bool(row["Automatic_Decision_Allowed"]) is False
    assert row["Production_Authority"] == "NONE"
    assert row["Source_Version"] == CALIBRATION_GATE_VERSION
    assert "mature_cells=8/8" in row["Secondary_Progress"]


def test_calibration_below_existing_sample_threshold_does_not_trigger() -> None:
    packet = inject_multicell_reviews(
        pd.DataFrame(),
        pd.DataFrame(),
        _calibration(starts=CALIBRATION_MIN_OOS_STARTS - 1),
        pd.DataFrame(),
        REFRESH,
    )
    assert packet.empty


def test_starter_role_requires_all_six_frozen_cells() -> None:
    packet = inject_multicell_reviews(
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        _role(complete=False),
        REFRESH,
    )
    assert packet.empty


def test_starter_role_full_maturity_injects_one_manual_review_case() -> None:
    packet = inject_multicell_reviews(
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        _role(),
        REFRESH,
    )
    assert len(packet) == 1
    row = packet.iloc[0]
    assert row["Lane"] == "Starter Role Live Shadow"
    assert row["Review_Trigger"] == REVIEW_TRIGGER
    assert row["Status"] == "FAIL"
    assert int(row["Current_Starts"]) == ROLE_MIN_RESOLVED_STARTS
    assert int(row["Required_Starts"]) == ROLE_MIN_RESOLVED_STARTS
    assert int(row["Current_Breadth"]) == len(REQUIRED_ROLES) * len(REQUIRED_METRICS)
    assert bool(row["Ready_For_Manual_Review"]) is True
    assert row["Production_Authority"] == "NONE"
    assert row["Source_Version"] == ROLE_GATE_VERSION
    assert "mature_cells=6/6" in row["Secondary_Progress"]


def test_existing_queue_dedupes_same_lane_trigger_and_gate_version() -> None:
    existing_queue = pd.DataFrame(
        [
            {
                "Lane": "Calibration Shadow",
                "Review_Trigger": REVIEW_TRIGGER,
                "Source_Version": CALIBRATION_GATE_VERSION,
            }
        ]
    )
    packet = inject_multicell_reviews(
        pd.DataFrame(),
        existing_queue,
        _calibration(),
        pd.DataFrame(),
        REFRESH,
    )
    assert packet.empty


def test_current_packet_case_suppresses_duplicate_multicell_case() -> None:
    current = inject_multicell_reviews(
        pd.DataFrame(),
        pd.DataFrame(),
        _calibration(),
        pd.DataFrame(),
        REFRESH,
    )
    current.loc[0, "Review_Trigger"] = "STATUS_TRANSITION"
    packet = inject_multicell_reviews(
        current,
        pd.DataFrame(),
        _calibration(),
        pd.DataFrame(),
        REFRESH,
    )
    assert len(packet) == 1
    assert packet.iloc[0]["Review_Trigger"] == "STATUS_TRANSITION"


def test_injected_case_recomputes_packet_summary_and_queues_durably() -> None:
    packet = inject_multicell_reviews(
        pd.DataFrame(),
        pd.DataFrame(),
        _calibration(),
        pd.DataFrame(),
        REFRESH,
    )
    summary = build_packet_summary(packet, pd.DataFrame(), REFRESH)
    assert summary.iloc[0]["Packet_Status"] == "MANUAL_REVIEW_PACKET_READY"
    assert int(summary.iloc[0]["Triggered_Lanes"]) == 1
    assert int(summary.iloc[0]["Status_Transition_Lanes"]) == 0
    assert int(summary.iloc[0]["Readiness_Transition_Lanes"]) == 0

    queue = append_review_queue(packet, pd.DataFrame(), REFRESH)
    queue_summary = build_queue_summary(queue, REFRESH)
    assert len(queue) == 1
    assert queue.iloc[0]["Review_Trigger"] == REVIEW_TRIGGER
    assert queue.iloc[0]["Review_Status"] == "PENDING_MANUAL_REVIEW"
    assert queue_summary.iloc[0]["Queue_Status"] == "PENDING_MANUAL_REVIEW"
    assert int(queue_summary.iloc[0]["Pending_Cases"]) == 1
    assert bool(queue.iloc[0]["Automatic_Decision_Allowed"]) is False
    assert queue.iloc[0]["Production_Authority"] == "NONE"


def test_report_only_controls_are_frozen() -> None:
    assert VERSION == "research-multicell-review-injector-v1-report-only"
    assert REVIEW_TRIGGER == "MULTICELL_MATURITY_TRANSITION"
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert NO_AUTO_PROMOTION is True
    assert AUTOMATIC_DECISION_ALLOWED is False
