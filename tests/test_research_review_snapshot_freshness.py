from __future__ import annotations

from pathlib import Path

import pandas as pd

import training.confirmed_lineup_review_snapshot as lineup_review
import training.research_review_snapshot_freshness as freshness
import training.umpire_context_review_snapshot as umpire_review


def _lineup_source() -> tuple[pd.DataFrame, pd.DataFrame]:
    gate = pd.DataFrame([{
        "OOS_Paired_Starts": 12, "Observed_Days": 3, "Distinct_Opponents": 8,
        "Manual_Review_Ready": False, "Evidence_Status": "LEARNING", "Reason": "learning",
        "Preconfirm_MAE": 1.5, "Confirmed_MAE": 1.4, "Relative_MAE_Improvement": 0.01,
        "Confirmed_Win_Share": 0.55, "Confirmed_Loss_Share": 0.45,
        "Preconfirm_Bias": 0.10, "Confirmed_Bias": 0.09, "Mean_Absolute_Projection_Delta": 0.05,
        "Report_Only": True, "Production_Authority": "NONE",
        "Validation_Version": "lineup-k-walkforward-v2-lineage-safe-report-only",
    }])
    segments = pd.DataFrame([{
        "Dimension": "OVERALL", "Segment": "ALL", "Rows": 12, "Authentic_Pregame_Pairs": 12,
        "OOS_Paired_Starts": 12, "Observed_Days": 3, "Distinct_Opponents": 8,
        "Preconfirm_MAE": 1.5, "Confirmed_MAE": 1.4, "Relative_MAE_Improvement": 0.01,
        "Confirmed_Win_Share": 0.55, "Confirmed_Loss_Share": 0.45,
        "Preconfirm_Bias": 0.10, "Confirmed_Bias": 0.09, "Mean_Absolute_Projection_Delta": 0.05,
        "Evidence": "synthetic", "Reason": "learning", "Report_Only": True,
        "Production_Authority": "NONE",
        "Validation_Version": "lineup-k-walkforward-v2-lineage-safe-report-only",
    }])
    return gate, segments


def _umpire_source() -> tuple[pd.DataFrame, pd.DataFrame]:
    gate = pd.DataFrame([{
        "OOS_Eligible_Starts": 15, "Observed_Days": 4, "Distinct_Umpires": 9,
        "Manual_Review_Ready": False, "Evidence_Status": "LEARNING", "Recommended_Action": "KEEP_LEARNING",
        "Reason": "learning", "Base_MAE": 1.5, "UmpireCandidate_MAE": 1.45,
        "Relative_MAE_Improvement": 0.01, "Candidate_Win_Share": 0.55, "Candidate_Loss_Share": 0.45,
        "Base_Bias": 0.10, "UmpireCandidate_Bias": 0.09, "Mean_Absolute_Factor_Delta": 0.02,
        "Report_Only": True, "Production_Authority": "NONE",
        "Validation_Version": "umpire-k-live-validation-v1-lineage-safe-report-only",
    }])
    segments = pd.DataFrame([{
        "Dimension": "OVERALL", "Segment": "ALL", "Rows": 15, "Authentic_Pregame_Candidates": 15,
        "OOS_Eligible_Starts": 15, "Observed_Days": 4, "Distinct_Umpires": 9,
        "Base_MAE": 1.5, "UmpireCandidate_MAE": 1.45, "Relative_MAE_Improvement": 0.01,
        "Candidate_Win_Share": 0.55, "Candidate_Loss_Share": 0.45,
        "Base_Bias": 0.10, "UmpireCandidate_Bias": 0.09, "Mean_Absolute_Factor_Delta": 0.02,
        "Evidence": "synthetic", "Reason": "learning", "Report_Only": True,
        "Production_Authority": "NONE",
        "Validation_Version": "umpire-k-live-validation-v1-lineage-safe-report-only",
    }])
    return gate, segments


def _write_all(root: Path) -> None:
    lineup_gate, lineup_segments = _lineup_source()
    lineup_gate.to_csv(root / "lineup_k_walkforward_gate.csv", index=False)
    lineup_segments.to_csv(root / "lineup_k_walkforward_segments.csv", index=False)
    lineup_snapshot = lineup_review.build_review_snapshot(lineup_segments)
    lineup_summary = lineup_review.build_review_summary(lineup_gate, lineup_snapshot)
    lineup_snapshot.to_csv(root / "confirmed_lineup_review_snapshot.csv", index=False)
    lineup_summary.to_csv(root / "confirmed_lineup_review_summary.csv", index=False)

    umpire_gate, umpire_segments = _umpire_source()
    umpire_gate.to_csv(root / "umpire_k_live_validation_gate.csv", index=False)
    umpire_segments.to_csv(root / "umpire_k_live_validation_segments.csv", index=False)
    umpire_snapshot = umpire_review.build_review_snapshot(umpire_segments)
    umpire_summary = umpire_review.build_review_summary(umpire_gate, umpire_snapshot)
    umpire_snapshot.to_csv(root / "umpire_context_review_snapshot.csv", index=False)
    umpire_summary.to_csv(root / "umpire_context_review_summary.csv", index=False)


def test_both_review_artifacts_certify_current(tmp_path: Path) -> None:
    _write_all(tmp_path)
    detail = freshness.build_review_snapshot_freshness(tmp_path)
    summary = freshness.build_freshness_summary(detail).iloc[0]
    assert detail["Freshness_Status"].tolist() == [freshness.CURRENT, freshness.CURRENT]
    assert summary["Overall_Status"] == "HEALTHY"
    assert int(summary["Current_Artifacts"]) == 2


def test_changed_source_marks_saved_snapshot_stale(tmp_path: Path) -> None:
    _write_all(tmp_path)
    segments = pd.read_csv(tmp_path / "lineup_k_walkforward_segments.csv")
    segments.loc[0, "Confirmed_MAE"] = 1.2
    segments.to_csv(tmp_path / "lineup_k_walkforward_segments.csv", index=False)
    detail = freshness.build_review_snapshot_freshness(tmp_path).set_index("Review_Artifact")
    summary = freshness.build_freshness_summary(detail.reset_index()).iloc[0]
    assert detail.loc["CONFIRMED_LINEUP_REVIEW", "Freshness_Status"] == freshness.DERIVED_DRIFT
    assert detail.loc["UMPIRE_CONTEXT_REVIEW", "Freshness_Status"] == freshness.CURRENT
    assert summary["Overall_Status"] == "STALE"


def test_missing_saved_summary_is_incomplete(tmp_path: Path) -> None:
    _write_all(tmp_path)
    (tmp_path / "umpire_context_review_summary.csv").unlink()
    detail = freshness.build_review_snapshot_freshness(tmp_path).set_index("Review_Artifact")
    summary = freshness.build_freshness_summary(detail.reset_index()).iloc[0]
    assert detail.loc["UMPIRE_CONTEXT_REVIEW", "Freshness_Status"] == freshness.DERIVED_MISSING
    assert summary["Overall_Status"] == "INCOMPLETE"


def test_missing_source_is_incomplete(tmp_path: Path) -> None:
    _write_all(tmp_path)
    (tmp_path / "lineup_k_walkforward_segments.csv").unlink()
    detail = freshness.build_review_snapshot_freshness(tmp_path).set_index("Review_Artifact")
    assert detail.loc["CONFIRMED_LINEUP_REVIEW", "Freshness_Status"] == freshness.SOURCE_MISSING
    assert freshness.build_freshness_summary(detail.reset_index()).iloc[0]["Overall_Status"] == "INCOMPLETE"


def test_freshness_controls_are_report_only() -> None:
    assert freshness.VERSION == "research-review-snapshot-freshness-v1-report-only"
    assert freshness.REPORT_ONLY is True
    assert freshness.PRODUCTION_AUTHORITY == "NONE"
    assert freshness.NO_AUTO_PROMOTION is True
    assert freshness.AUTOMATIC_DECISION_ALLOWED is False
    assert len(freshness.SPECS) == 2
