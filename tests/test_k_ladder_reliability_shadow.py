from __future__ import annotations

import pandas as pd

from engine.starter_history import HISTORY_SEMANTICS
from training.k_ladder_reliability_shadow import build_cohort_summary, build_detail, build_gate


def test_ladder_shadow_tracks_model_supported_target_not_exact_projection() -> None:
    history = pd.DataFrame([
        {
            "pitcher_id": 1,
            "player": "Pitcher A",
            "game_date": "2026-08-20",
            "projection": 5.8,
            "actual_strikeouts": 5,
            "sim_5p": 0.60,
            "math_5p": 0.80,
            "confidence": "HIGH",
            "data_quality": 92,
            "history_semantics": HISTORY_SEMANTICS,
        }
    ])
    row = build_detail(history).iloc[0]

    assert row["K_Target"] == 5
    assert row["Target_Label"] == "5+"
    assert bool(row["Ladder_Win"])
    assert row["Projection_Headroom"] == 0.8
    assert row["Target_Probability"] == 0.7
    assert abs(float(row["Brier"]) - 0.09) < 1e-12
    assert row["Production_Authority"] == "NONE"
    assert bool(row["Report_Only"])
    assert bool(row["No_Projection_Adjustment"])


def test_ladder_shadow_maturity_remains_manual_review_only() -> None:
    rows = []
    for index in range(60):
        target = 5
        rows.append({
            "pitcher_id": index % 20,
            "player": f"Pitcher {index % 20}",
            "game_date": f"2026-08-{10 + (index % 10):02d}",
            "projection": 5.5,
            "actual_strikeouts": 5 if index % 3 else 4,
            "sim_5p": 0.70,
            "math_5p": 0.72,
            "confidence": "HIGH",
            "data_quality": 90,
            "history_semantics": HISTORY_SEMANTICS,
        })
    detail = build_detail(pd.DataFrame(rows))
    cohorts = build_cohort_summary(detail)
    gate = build_gate(detail, cohorts).iloc[0]

    assert gate["Status"] == "READY_FOR_MANUAL_RESEARCH_REVIEW"
    assert bool(gate["Ready_For_Manual_Review"])
    assert gate["Recommended_Action"] == "MANUAL_RESEARCH_REVIEW"
    assert gate["Probability_Coverage"] == 1.0
    assert gate["Production_Authority"] == "NONE"
    assert bool(gate["Report_Only"])
    assert bool(gate["No_Projection_Adjustment"])
    assert "sportsbook" in str(gate["Reason"]).lower()
