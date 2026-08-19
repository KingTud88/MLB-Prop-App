from __future__ import annotations

import pandas as pd
import pytest

import training.research_milestone_watch as watch


def _row(**overrides: object) -> dict[str, object]:
    row = {
        "Lane": "Synthetic Lane",
        "Category": "TEST",
        "Status": "LEARNING",
        "Required_Starts": 30,
        "Starts_Remaining": 3,
        "Required_Days": 10,
        "Days_Remaining": 4,
        "Breadth_Label": "OPPONENTS",
        "Required_Breadth": 8,
        "Breadth_Remaining": 0,
        "Secondary_Progress": "secondary frozen requirement",
        "Ready_For_Manual_Review": False,
        "Recommended_Action": "KEEP_LEARNING",
        "Source_Reason": "synthetic reason",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "No_Auto_Promotion": True,
        "Source_Version": "synthetic-v1",
    }
    row.update(overrides)
    return row


def test_lists_exact_primary_blockers_without_scoring() -> None:
    result = watch.build_milestone_watch(pd.DataFrame([_row()])).iloc[0]
    assert result["Primary_Gate_State"] == "PRIMARY_DIMENSIONS_BLOCKED"
    assert result["Blocking_Dimensions"] == "STARTS=3|DAYS=4"
    assert result["Secondary_Progress"] == "secondary frozen requirement"
    assert "Score" not in watch.WATCH_COLUMNS


def test_primary_maturity_does_not_claim_manual_review_readiness() -> None:
    result = watch.build_milestone_watch(
        pd.DataFrame([_row(Starts_Remaining=0, Days_Remaining=0, Breadth_Remaining=0)])
    ).iloc[0]
    assert result["Primary_Gate_State"] == "PRIMARY_DIMENSIONS_MATURE"
    assert bool(result["Ready_For_Manual_Review"]) is False


def test_nonstandard_gate_is_preserved_without_invented_requirements() -> None:
    result = watch.build_milestone_watch(
        pd.DataFrame([
            _row(
                Lane="Calibration Shadow",
                Required_Starts=None,
                Starts_Remaining=None,
                Required_Days=None,
                Days_Remaining=None,
                Required_Breadth=None,
                Breadth_Remaining=None,
            )
        ])
    ).iloc[0]
    assert result["Primary_Gate_State"] == "NONSTANDARD_GATE_TRACKED_ELSEWHERE"
    assert result["Blocking_Dimensions"] == ""


def test_source_manual_review_ready_remains_authoritative() -> None:
    result = watch.build_milestone_watch(pd.DataFrame([_row(Ready_For_Manual_Review=True)])).iloc[0]
    assert result["Primary_Gate_State"] == "MANUAL_REVIEW_READY"


def test_control_violation_fails_closed() -> None:
    with pytest.raises(ValueError):
        watch.build_milestone_watch(pd.DataFrame([_row(Production_Authority="PRODUCTION")]))


def test_summary_and_controls_are_report_only() -> None:
    frame = watch.build_milestone_watch(
        pd.DataFrame([
            _row(),
            _row(Lane="Mature", Starts_Remaining=0, Days_Remaining=0, Breadth_Remaining=0),
            _row(
                Lane="Nonstandard",
                Required_Starts=None,
                Starts_Remaining=None,
                Required_Days=None,
                Days_Remaining=None,
                Required_Breadth=None,
                Breadth_Remaining=None,
            ),
        ])
    )
    summary = watch.build_watch_summary(frame).iloc[0]
    assert int(summary["Total_Lanes"]) == 3
    assert int(summary["Primary_Dimensions_Blocked_Lanes"]) == 1
    assert int(summary["Primary_Dimensions_Mature_Lanes"]) == 1
    assert int(summary["Nonstandard_Gate_Lanes"]) == 1
    assert watch.REPORT_ONLY is True
    assert watch.PRODUCTION_AUTHORITY == "NONE"
    assert watch.NO_AUTO_PROMOTION is True
    assert watch.AUTOMATIC_DECISION_ALLOWED is False
