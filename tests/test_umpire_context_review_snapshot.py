from __future__ import annotations

import pandas as pd

from training.umpire_context_review_snapshot import (
    AUTOMATIC_DECISION_ALLOWED,
    NO_AUTO_PROMOTION,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    REVIEW_DIMENSIONS,
    build_review_snapshot,
    build_review_summary,
)


def _gate(*, days: int, status: str = "LEARNING", review_ready: bool = False) -> pd.DataFrame:
    return pd.DataFrame([{
        "Evidence_Status": status,
        "Captured_Candidates": 139,
        "Authentic_Pregame_Candidates": 104,
        "OOS_Eligible_Starts": 104,
        "Observed_Days": days,
        "Distinct_Umpires": 46,
        "Base_MAE": 1.75,
        "UmpireCandidate_MAE": 1.77,
        "Relative_MAE_Improvement": -0.0084,
        "Candidate_Win_Share": 0.462,
        "Candidate_Loss_Share": 0.538,
        "Base_Bias": 0.22,
        "UmpireCandidate_Bias": 0.224,
        "Mean_Absolute_Factor_Delta": 0.031,
        "Reason": "Frozen source reason.",
        "Manual_Review_Ready": review_ready,
        "Recommended_Action": "KEEP_LEARNING" if not review_ready else "MANUAL_REVIEW_READY",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "Validation_Version": "umpire-k-live-validation-v1-lineage-safe-report-only",
    }])


def _segments() -> pd.DataFrame:
    rows = []
    for dimension, segment in (
        ("OVERALL", "ALL LIVE UMPIRE CANDIDATES"),
        ("LINEAGE", "PRE_GAME_CAPTURE"),
        ("OUTCOME LINEAGE", "RESOLVED_AFTER_START"),
        ("FACTOR DIRECTION", "K UP"),
        ("FACTOR DIRECTION", "K DOWN"),
        ("FACTOR DELTA BAND", "1-1.9%"),
        ("PRIOR UMPIRE GAMES BAND", "40+"),
        ("QUALITY BAND", "70-79"),
        ("STARTER HISTORY BAND", "10+"),
    ):
        rows.append({
            "Dimension": dimension,
            "Segment": segment,
            "Rows": 50,
            "Authentic_Pregame_Candidates": 45,
            "OOS_Eligible_Starts": 40,
            "Observed_Days": 10,
            "Distinct_Umpires": 20,
            "Base_MAE": 1.8,
            "UmpireCandidate_MAE": 1.7,
            "Relative_MAE_Improvement": 0.055,
            "Candidate_Win_Share": 0.55,
            "Candidate_Loss_Share": 0.45,
            "Base_Bias": 0.20,
            "UmpireCandidate_Bias": 0.10,
            "Mean_Absolute_Factor_Delta": 0.02,
            "Evidence": "SUPPORTED",
            "Reason": "Synthetic segment.",
            "Report_Only": True,
            "Production_Authority": "NONE",
            "Validation_Version": "umpire-k-live-validation-v1-lineage-safe-report-only",
        })
    return pd.DataFrame(rows)


def test_before_ten_days_stays_learning_without_human_review() -> None:
    snapshot = build_review_snapshot(_segments())
    summary = build_review_summary(_gate(days=9), snapshot).iloc[0]
    assert summary["Review_Status"] == "LEARNING"
    assert bool(summary["Minimum_Evaluation_Ready"]) is False
    assert bool(summary["Human_Review_Required"]) is False
    assert summary["Recommended_Action"] == "COLLECT_UNTIL_MINIMUM_EVALUATION"


def test_ten_day_caution_forces_diagnostic_review_without_promotion() -> None:
    snapshot = build_review_snapshot(_segments())
    summary = build_review_summary(_gate(days=10, status="CAUTION", review_ready=False), snapshot).iloc[0]
    assert summary["Review_Status"] == "MINIMUM_EVALUATION_REVIEW_REQUIRED"
    assert bool(summary["Minimum_Evaluation_Ready"]) is True
    assert bool(summary["Source_Manual_Review_Ready"]) is False
    assert bool(summary["Human_Review_Required"]) is True
    assert summary["Recommended_Action"] == "REVIEW_FROZEN_UMPIRE_EVIDENCE_NO_AUTOMATIC_PROMOTION"
    assert bool(summary["Automatic_Decision_Allowed"]) is False
    assert summary["Production_Authority"] == "NONE"


def test_source_promotion_ready_is_still_manual_only() -> None:
    snapshot = build_review_snapshot(_segments())
    summary = build_review_summary(
        _gate(days=20, status="STRONG EVIDENCE", review_ready=True),
        snapshot,
    ).iloc[0]
    assert summary["Review_Status"] == "PROMOTION_REVIEW_READY"
    assert bool(summary["Source_Manual_Review_Ready"]) is True
    assert summary["Recommended_Action"] == "MANUAL_PROMOTION_REVIEW_ONLY"
    assert bool(summary["Automatic_Decision_Allowed"]) is False
    assert bool(summary["No_Auto_Promotion"]) is True


def test_snapshot_packages_existing_frozen_diagnostics_only() -> None:
    source = _segments()
    snapshot = build_review_snapshot(source)
    assert set(snapshot["Dimension"]) == set(REVIEW_DIMENSIONS)
    assert {
        "FACTOR_DIRECTION",
        "FACTOR_MAGNITUDE",
        "PRIOR_UMPIRE_SAMPLE",
        "DATA_QUALITY",
        "STARTER_HISTORY",
        "LINEAGE_INTEGRITY",
    }.issubset(set(snapshot["Review_Dimension"]))
    assert int(snapshot.iloc[0]["OOS_Eligible_Starts"]) == int(source.iloc[0]["OOS_Eligible_Starts"])
    assert set(snapshot["Production_Authority"]) == {"NONE"}
    assert set(snapshot["Report_Only"]) == {True}
    assert set(snapshot["No_Auto_Promotion"]) == {True}


def test_control_violation_in_source_is_rejected() -> None:
    bad = _segments()
    bad.loc[0, "Production_Authority"] = "MODEL"
    try:
        build_review_snapshot(bad)
    except ValueError as exc:
        assert "contract" in str(exc)
    else:
        raise AssertionError("Expected report-only contract violation to fail closed.")


def test_constants_are_frozen_report_only() -> None:
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert NO_AUTO_PROMOTION is True
    assert AUTOMATIC_DECISION_ALLOWED is False
