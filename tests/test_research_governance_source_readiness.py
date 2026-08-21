from __future__ import annotations

from pathlib import Path

import pandas as pd

from training.research_promotion_command_center import build_promotion_command_center


def _write(path: Path, name: str, rows: list[dict[str, object]]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path / name, index=False)


def test_ml_helping_can_reach_manual_review_only_with_governance_breadth(tmp_path: Path) -> None:
    _write(tmp_path, "ml_shadow_summary.csv", [{
        "Challenger": "ML_SHADOW",
        "OOS_Starts": 60,
        "Existing_MAE": 2.0,
        "Candidate_MAE": 1.8,
        "Relative_MAE_Improvement": 0.10,
        "Candidate_Win_Share": 0.60,
        "Existing_Bias": 0.2,
        "Candidate_Bias": 0.1,
        "Status": "HELPING",
        "Reason": "passed",
        "Report_Only": True,
        "Live_Projection_Use": False,
        "Market_Features_Used": False,
        "Validation_Version": "ml-k-shadow-v1-report-only",
    }])
    detail = []
    for day in range(1, 11):
        for pitcher in range(20):
            detail.append({
                "game_date": f"2026-08-{day:02d}",
                "pitcher_id": pitcher,
                "opponent": f"OPP{pitcher % 15}",
                "OOS_Eligible": True,
                "ML_Shadow_Projection": 5.0,
            })
    _write(tmp_path, "ml_shadow_detail.csv", detail)
    row = build_promotion_command_center(tmp_path).set_index("Lane").loc["ML Challenger"]
    assert row["Status"] == "HELPING"
    assert bool(row["Ready_For_Manual_Review"])
    assert row["Recommended_Action"] == "MANUAL_RESEARCH_REVIEW_ONLY"
    assert row["Production_Authority"] == "NONE"


def test_calibration_pass_still_requires_governance_metadata_and_breadth(tmp_path: Path) -> None:
    gate = []
    for milestone in range(3, 11):
        gate.append({
            "Milestone": milestone,
            "OOS_Starts": 50,
            "Promotion_Gate_Status": "PASS",
            "Reasons": "",
            "Gate_Version": "calibration-shadow-gate-v1",
        })
    _write(tmp_path, "calibration_shadow_gate.csv", gate)
    detail = []
    for day in range(1, 11):
        for pitcher in range(20):
            detail.append({"game_date": f"2026-08-{day:02d}", "pitcher_id": pitcher})
    _write(tmp_path, "calibration_shadow_detail.csv", detail)
    row = build_promotion_command_center(tmp_path).set_index("Lane").loc["Calibration Shadow"]
    assert row["Status"] == "PASS"
    assert bool(row["Ready_For_Manual_Review"])
    assert row["Recommended_Action"] == "MANUAL_RESEARCH_REVIEW_ONLY"
    assert row["Production_Authority"] == "NONE"
