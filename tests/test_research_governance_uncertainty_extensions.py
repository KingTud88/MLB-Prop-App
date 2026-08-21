from __future__ import annotations

from pathlib import Path

import pandas as pd

from training.research_governance_v2 import build_uncertainty_report


def test_input_quality_primary_pairs_get_deterministic_paired_uncertainty(tmp_path: Path) -> None:
    pd.DataFrame([
        {
            "Rule": "primary_pregame_matched",
            "Metric": "STRIKEOUTS",
            "Pair_ID": 1,
            "Shallow_Game_Date": "2026-08-20",
            "Deep_Game_Date": "2026-08-21",
            "Absolute_Error_Delta_Shallow_Minus_Deep": 0.5,
        },
        {
            "Rule": "primary_pregame_matched",
            "Metric": "STRIKEOUTS",
            "Pair_ID": 2,
            "Shallow_Game_Date": "2026-08-21",
            "Deep_Game_Date": "2026-08-22",
            "Absolute_Error_Delta_Shallow_Minus_Deep": -0.1,
        },
        {
            "Rule": "same_pitcher_sensitivity",
            "Metric": "STRIKEOUTS",
            "Pair_ID": 3,
            "Shallow_Game_Date": "2026-08-22",
            "Deep_Game_Date": "2026-08-23",
            "Absolute_Error_Delta_Shallow_Minus_Deep": 99.0,
        },
    ]).to_csv(tmp_path / "input_quality_matched_v2_pairs.csv", index=False)

    first = build_uncertainty_report(tmp_path)
    second = build_uncertainty_report(tmp_path)
    assert first.equals(second)
    row = first.loc[
        first["Lane"].eq("Input Quality v2 · Strikeouts")
        & first["Metric"].eq("Shallow_Absolute_Error_minus_Deep_Absolute_Error")
    ].iloc[0]
    assert int(row["Observations"]) == 2
    assert int(row["Date_Blocks"]) == 2
    assert abs(float(row["Estimate"]) - 0.2) < 1e-12
    assert "paired bootstrap" in str(row["Method"])
    assert pd.notna(row["CI_Low_95"])
    assert pd.notna(row["CI_High_95"])
    assert bool(row["Report_Only"])
    assert row["Production_Authority"] == "NONE"


def test_calibration_common_mode_gets_future_detail_date_block_uncertainty(tmp_path: Path) -> None:
    pd.DataFrame([
        {
            "Game_Date": "2026-08-21",
            "Candidate_Ready": True,
            "Baseline_Absolute_Error": 2.0,
            "Candidate_Absolute_Error": 1.0,
        },
        {
            "Game_Date": "2026-08-21",
            "Candidate_Ready": True,
            "Baseline_Absolute_Error": 1.5,
            "Candidate_Absolute_Error": 1.0,
        },
        {
            "Game_Date": "2026-08-22",
            "Candidate_Ready": True,
            "Baseline_Absolute_Error": 1.0,
            "Candidate_Absolute_Error": 1.5,
        },
        {
            "Game_Date": "2026-08-22",
            "Candidate_Ready": False,
            "Baseline_Absolute_Error": 5.0,
            "Candidate_Absolute_Error": 0.0,
        },
    ]).to_csv(tmp_path / "calibration_common_mode_v2_detail.csv", index=False)

    report = build_uncertainty_report(tmp_path)
    row = report.loc[report["Lane"].eq("Calibration Common-Mode v2")].iloc[0]
    assert row["Metric"] == "Absolute_Error_Improvement"
    assert int(row["Observations"]) == 3
    assert int(row["Date_Blocks"]) == 2
    assert abs(float(row["Estimate"]) - (1.0 / 3.0)) < 1e-12
    assert pd.notna(row["CI_Low_95"])
    assert pd.notna(row["CI_High_95"])
    assert bool(row["Report_Only"])
    assert row["Production_Authority"] == "NONE"
