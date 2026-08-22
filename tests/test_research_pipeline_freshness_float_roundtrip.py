from __future__ import annotations

import pandas as pd

import training.research_pipeline_freshness_audit as freshness
from training.research_governance_v2 import UNCERTAINTY_COLUMNS


def _uncertainty_row(estimate: float) -> pd.DataFrame:
    return pd.DataFrame([{
        "Lane": "Calibration Shadow",
        "Segment": "Milestone 3",
        "Metric": "Baseline_Brier_minus_Candidate_Brier",
        "Estimate": estimate,
        "CI_Low_95": -0.0032555315242983047,
        "CI_High_95": 0.000556989003172647,
        "Observations": 209,
        "Date_Blocks": 8,
        "Method": "game-date block bootstrap; 1000 deterministic resamples",
        "Report_Only": True,
        "Production_Authority": "NONE",
        "Governance_Version": "research-governance-v2-report-only",
    }], columns=UNCERTAINTY_COLUMNS)


def test_governance_uncertainty_signature_ignores_csv_roundtrip_tail_noise() -> None:
    expected = _uncertainty_row(-0.0013061278371160237)
    persisted = _uncertainty_row(-0.001306127837116)

    exact_expected = freshness._frame_signature(
        expected,
        UNCERTAINTY_COLUMNS,
        ["Lane", "Segment", "Metric"],
    )
    exact_persisted = freshness._frame_signature(
        persisted,
        UNCERTAINTY_COLUMNS,
        ["Lane", "Segment", "Metric"],
    )
    assert exact_expected != exact_persisted

    stable_expected = freshness._frame_signature(
        expected,
        UNCERTAINTY_COLUMNS,
        ["Lane", "Segment", "Metric"],
        float_significant_digits=freshness.GOVERNANCE_UNCERTAINTY_SIGNATURE_DIGITS,
    )
    stable_persisted = freshness._frame_signature(
        persisted,
        UNCERTAINTY_COLUMNS,
        ["Lane", "Segment", "Metric"],
        float_significant_digits=freshness.GOVERNANCE_UNCERTAINTY_SIGNATURE_DIGITS,
    )
    assert stable_expected == stable_persisted


def test_governance_uncertainty_signature_still_detects_material_numeric_drift() -> None:
    expected = _uncertainty_row(-0.0013061278371160237)
    drifted = _uncertainty_row(-0.0014061278371160237)

    assert freshness._frame_signature(
        expected,
        UNCERTAINTY_COLUMNS,
        ["Lane", "Segment", "Metric"],
        float_significant_digits=freshness.GOVERNANCE_UNCERTAINTY_SIGNATURE_DIGITS,
    ) != freshness._frame_signature(
        drifted,
        UNCERTAINTY_COLUMNS,
        ["Lane", "Segment", "Metric"],
        float_significant_digits=freshness.GOVERNANCE_UNCERTAINTY_SIGNATURE_DIGITS,
    )
