from __future__ import annotations

import pandas as pd
import pytest

from engine.starter_history import HISTORY_SEMANTICS
from training.projection_crusher_shadow import build_cohort_summary, build_detail, build_gate


def test_crusher_shadow_uses_exact_frozen_projection_residual() -> None:
    history = pd.DataFrame([
        {
            "pitcher_id": 1,
            "player": "Pitcher A",
            "game_date": "2026-08-20",
            "projection": 5.8,
            "actual_strikeouts": 5,
            "confidence": "HIGH",
            "data_quality": 92,
            "history_semantics": HISTORY_SEMANTICS,
        },
        {
            "pitcher_id": 2,
            "player": "Pitcher B",
            "game_date": "2026-08-20",
            "projection": 5.8,
            "actual_strikeouts": 8,
            "confidence": "HIGH",
            "data_quality": 92,
            "history_semantics": HISTORY_SEMANTICS,
        },
    ])
    detail = build_detail(history).set_index("Pitcher")

    assert detail.loc["Pitcher A", "K_Residual"] == pytest.approx(-0.8)
    assert not bool(detail.loc["Pitcher A", "Beat_Projection"])
    assert detail.loc["Pitcher B", "K_Residual"] == pytest.approx(2.2)
    assert bool(detail.loc["Pitcher B", "Beat_Projection"])
    assert bool(detail.loc["Pitcher B", "Material_Crusher_Event"])
    assert set(detail["Production_Authority"].astype(str)) == {"NONE"}
    assert detail["Report_Only"].astype(bool).all()
    assert detail["No_Projection_Adjustment"].astype(bool).all()


def test_crusher_shadow_maturity_only_opens_manual_research_review() -> None:
    rows = []
    for index in range(60):
        rows.append({
            "pitcher_id": index % 20,
            "player": f"Pitcher {index % 20}",
            "game_date": f"2026-08-{10 + (index % 10):02d}",
            "projection": 5.25,
            "actual_strikeouts": 6 if index % 2 == 0 else 5,
            "confidence": "HIGH",
            "data_quality": 90,
            "history_semantics": HISTORY_SEMANTICS,
        })
    detail = build_detail(pd.DataFrame(rows))
    cohorts = build_cohort_summary(detail)
    gate = build_gate(detail, cohorts).iloc[0]

    assert gate["Status"] == "READY_FOR_MANUAL_RESEARCH_REVIEW"
    assert bool(gate["Ready_For_Manual_Review"])
    assert gate["Recommended_Action"] == "MANUAL_RESEARCH_REVIEW_THEN_FREEZE_FORWARD_CHALLENGER"
    assert gate["Production_Authority"] == "NONE"
    assert bool(gate["Report_Only"])
    assert bool(gate["No_Projection_Adjustment"])
