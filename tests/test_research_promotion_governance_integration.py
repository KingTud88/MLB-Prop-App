from __future__ import annotations

from pathlib import Path

import pandas as pd

from training.research_promotion_command_center import build_promotion_command_center


def _write_top_plays(path: Path, days: int) -> None:
    pd.DataFrame([{
        "Dimension": "OVERALL",
        "Segment": "ALL REAL-LINE TOP PLAYS",
        "Settled Legs": 40,
        "Observed Days": days,
        "Hits": 27,
        "Hit Rate": 0.675,
        "Avg Model Probability": 0.66,
        "Calibration Gap": 0.015,
        "Brier Score": 0.21,
        "Wilson Lower 95%": 0.52,
        "Evidence": "STRONG EVIDENCE",
        "Reason": "source-owned strong evidence",
        "Report Only": True,
        "Production Authority": "NONE",
        "Accountability Version": "top-plays-accountability-v1",
    }]).to_csv(path / "top_plays_accountability_summary.csv", index=False)


def test_promotion_center_applies_governance_v2_to_top_plays_readiness(tmp_path: Path) -> None:
    _write_top_plays(tmp_path, 4)
    blocked = build_promotion_command_center(tmp_path).set_index("Lane").loc["Top Plays Accountability"]
    assert blocked["Status"] == "STRONG EVIDENCE"
    assert int(blocked["Required_Days"]) == 5
    assert not bool(blocked["Ready_For_Manual_Review"])
    assert blocked["Recommended_Action"] == "COLLECT_GOVERNANCE_V2_BREADTH_BEFORE_MANUAL_REVIEW"

    _write_top_plays(tmp_path, 5)
    ready = build_promotion_command_center(tmp_path).set_index("Lane").loc["Top Plays Accountability"]
    assert ready["Status"] == "STRONG EVIDENCE"
    assert bool(ready["Ready_For_Manual_Review"])
    assert ready["Recommended_Action"] == "MANUAL_RESEARCH_REVIEW_ONLY"
    assert ready["Production_Authority"] == "NONE"
    assert bool(ready["No_Auto_Promotion"])
