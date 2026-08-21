import pandas as pd

from engine.starter_history import HISTORY_SEMANTICS
from training.projection_underperformer_shadow import (
    NO_PROJECTION_ADJUSTMENT,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    build_cohort_summary,
    build_detail,
    build_gate,
    build_pitcher_summary,
)


def _history(rows: int = 24, days: int = 6) -> pd.DataFrame:
    data = []
    for idx in range(rows):
        projected = 6.0 + (idx % 3) * 0.2
        under = idx % 4 != 0
        actual = projected - (2.2 if under else -0.8)
        data.append({
            "pitcher_id": 1000 + (idx % 8),
            "player": f"Pitcher {idx % 8}",
            "team": "AAA",
            "opponent": f"OPP{idx % 10}",
            "game_date": f"2026-08-{1 + (idx % days):02d}",
            "projection": projected,
            "actual_strikeouts": actual,
            "confidence": "HIGH" if idx % 2 == 0 else "MEDIUM",
            "data_quality": 90 if idx % 3 == 0 else 80,
            "opponent_k_pct": 0.26 if idx % 2 == 0 else 0.20,
            "lineup_confirmed": idx % 2 == 0,
            "starter_role_label": "ESTABLISHED",
            "leash_label": "NORMAL",
            "sim_mean_k": projected + 0.4,
            "math_mean_k": projected - 0.2,
            "k_sd": 1.5,
            "history_semantics": HISTORY_SEMANTICS,
        })
    return pd.DataFrame(data)


def test_underperformer_detail_uses_exact_frozen_residual_and_is_report_only():
    detail = build_detail(_history())
    assert not detail.empty
    first = detail.iloc[0]
    assert first["K_Residual"] == first["Actual_K"] - first["Projection"]
    assert bool(first["Below_Projection"]) is False
    assert bool(detail.iloc[1]["Below_Projection"]) is True
    assert bool(detail.iloc[1]["Material_Underperform_Event"]) is True
    assert detail["Report_Only"].eq(REPORT_ONLY).all()
    assert detail["Production_Authority"].eq(PRODUCTION_AUTHORITY).all()
    assert detail["No_Projection_Adjustment"].eq(NO_PROJECTION_ADJUSTMENT).all()


def test_underperformer_pitcher_and_cohort_summaries_preserve_negative_evidence():
    detail = build_detail(_history())
    pitchers = build_pitcher_summary(detail)
    cohorts = build_cohort_summary(detail)
    assert not pitchers.empty
    assert "Below_Projection_Rate" in pitchers.columns
    assert "Median_K_Residual" in pitchers.columns
    assert "Material_Underperform_Events" in pitchers.columns
    assert not cohorts.empty
    assert "UNDERINDEX" in set(cohorts["Signal"]) or "LEARNING" in set(cohorts["Signal"]) or "NEUTRAL" in set(cohorts["Signal"])
    assert cohorts["Production_Authority"].eq("NONE").all()


def test_underperformer_gate_never_authorizes_production_change():
    detail = build_detail(_history(rows=70, days=10))
    # Ensure breadth gate is mature independently of repeated pitcher names.
    detail["Pitcher"] = [f"Pitcher {idx % 25}" for idx in range(len(detail))]
    cohorts = build_cohort_summary(detail)
    gate = build_gate(detail, cohorts).iloc[0]
    assert gate["Status"] == "READY_FOR_MANUAL_RESEARCH_REVIEW"
    assert bool(gate["Ready_For_Manual_Review"]) is True
    assert gate["Recommended_Action"] == "MANUAL_RESEARCH_REVIEW_THEN_FREEZE_FORWARD_CHALLENGER"
    assert bool(gate["Report_Only"]) is True
    assert gate["Production_Authority"] == "NONE"
    assert bool(gate["No_Projection_Adjustment"]) is True


def test_future_or_legacy_outcomes_are_not_reconstructed_into_current_shadow():
    frame = pd.DataFrame([
        {"player": "Legacy", "projection": 7.0, "actual_strikeouts": 1, "history_semantics": "legacy"},
        {"player": "Current", "projection": 6.0, "actual_strikeouts": 4, "history_semantics": HISTORY_SEMANTICS},
        {"player": "Pending", "projection": 6.0, "actual_strikeouts": None, "history_semantics": HISTORY_SEMANTICS},
    ])
    detail = build_detail(frame)
    assert detail["Pitcher"].tolist() == ["Current"]
    assert detail.iloc[0]["K_Residual"] == -2.0
