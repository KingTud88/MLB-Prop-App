from __future__ import annotations

import pandas as pd
import pytest

from engine.starter_history import HISTORY_SEMANTICS
from training.projection_underperformer_forward_challenger import (
    AUTOMATIC_DECISION_ALLOWED,
    FIRST_ELIGIBLE_GAME_DATE,
    MIN_GLOBAL_PITCHERS,
    MIN_GLOBAL_RESOLVED_DAYS,
    MIN_GLOBAL_RESOLVED_STARTS,
    MIN_RULE_STARTS,
    NO_AUTO_PROMOTION,
    NO_PROJECTION_ADJUSTMENT,
    OVERINDEX_RESIDUAL_LIFT,
    PREREGISTERED_GAME_DATE,
    PROMOTION_ROW_REGISTERED,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    SUPPORTING_DIAGNOSTIC_ONLY,
    UNDERINDEX_RESIDUAL_LIFT,
    VERSION,
    build_evaluation,
    build_forward_detail,
    build_preregistration,
    build_summary,
)


def _history_row(
    game_date: str,
    idx: int,
    *,
    residual: float = -1.0,
    confidence: str = "HIGH",
    data_quality: float = 80.0,
    leash: str = "NORMAL",
) -> dict[str, object]:
    projection = 6.0
    return {
        "pitcher_id": 1000 + idx,
        "player": f"Pitcher {idx}",
        "team": "AAA",
        "opponent": f"OPP{idx % 8}",
        "game_date": game_date,
        "projection": projection,
        "actual_strikeouts": projection + residual,
        "confidence": confidence,
        "data_quality": data_quality,
        "opponent_k_pct": 0.23,
        "lineup_confirmed": True,
        "starter_role_label": "ESTABLISHED",
        "leash_label": leash,
        "sim_mean_k": 6.1,
        "math_mean_k": 5.9,
        "k_sd": 1.5,
        "history_semantics": HISTORY_SEMANTICS,
    }


def _synthetic_forward_detail() -> pd.DataFrame:
    rows = []
    for idx in range(MIN_GLOBAL_RESOLVED_STARTS):
        medium_flag = idx < MIN_RULE_STARTS
        residual = -1.0 if medium_flag else 0.0
        rows.append(
            {
                "Game_Date": f"2026-09-{1 + idx % MIN_GLOBAL_RESOLVED_DAYS:02d}",
                "Pitcher": f"Pitcher {idx % MIN_GLOBAL_PITCHERS}",
                "K_Residual": residual,
                "Below_Projection": residual < 0.0,
                "Material_Underperform_Event": residual <= -2.0,
                "Flag_Confidence_MEDIUM": medium_flag,
                "Flag_Data_Quality_LT50": False,
                "Flag_Leash_TIGHT": False,
            }
        )
    return pd.DataFrame(rows)


def test_preregistration_freezes_only_reviewed_mature_underindex_hypotheses() -> None:
    prereg = build_preregistration()
    assert prereg["Rule_ID"].tolist() == [
        "CONFIDENCE_MEDIUM",
        "DATA_QUALITY_LT50",
        "LEASH_TIGHT",
    ]
    assert prereg["Historical_Signal"].eq("UNDERINDEX").all()
    assert prereg["Historical_Resolved_Starts"].tolist() == [35, 16, 77]
    assert prereg["Historical_Residual_Lift"].tolist() == pytest.approx(
        [-0.7210022413336374, -0.7328345612382103, -0.588076249239811]
    )
    assert prereg["First_Eligible_Game_Date"].eq("2026-08-23").all()
    assert prereg["Rule_Min_Starts"].eq(15).all()
    assert prereg["Underindex_Residual_Lift_Threshold"].eq(-0.50).all()
    assert prereg["Supporting_Diagnostic_Only"].eq(True).all()
    assert prereg["Promotion_Row_Registered"].eq(False).all()


def test_forward_detail_strictly_excludes_review_selection_sample() -> None:
    history = pd.DataFrame(
        [
            _history_row(
                "2026-08-22",
                1,
                residual=-3.0,
                confidence="MEDIUM",
                data_quality=40.0,
                leash="TIGHT",
            ),
            _history_row(
                "2026-08-23",
                2,
                residual=-2.0,
                confidence="MEDIUM",
                data_quality=40.0,
                leash="TIGHT",
            ),
        ]
    )
    detail = build_forward_detail(history)
    assert detail["Game_Date"].tolist() == ["2026-08-23"]
    row = detail.iloc[0]
    assert bool(row["Flag_Confidence_MEDIUM"]) is True
    assert bool(row["Flag_Data_Quality_LT50"]) is True
    assert bool(row["Flag_Leash_TIGHT"]) is True
    assert bool(row["Any_Preregistered_Risk_Flag"]) is True
    assert row["K_Residual"] == pytest.approx(-2.0)
    assert row["Production_Authority"] == "NONE"
    assert bool(row["No_Projection_Adjustment"]) is True


def test_mature_future_rule_uses_frozen_residual_lift_and_manual_review_only() -> None:
    evaluation = build_evaluation(_synthetic_forward_detail())
    medium = evaluation.loc[evaluation["Rule_ID"].eq("CONFIDENCE_MEDIUM")].iloc[0]
    assert medium["Future_Resolved_Starts"] == MIN_GLOBAL_RESOLVED_STARTS
    assert medium["Future_Resolved_Days"] == MIN_GLOBAL_RESOLVED_DAYS
    assert medium["Future_Distinct_Pitchers"] == MIN_GLOBAL_PITCHERS
    assert medium["Flagged_Starts"] == MIN_RULE_STARTS
    assert medium["Flagged_Mean_K_Residual"] == pytest.approx(-1.0)
    assert medium["Future_Overall_Mean_K_Residual"] == pytest.approx(-0.25)
    assert medium["Residual_Lift_vs_Future_Overall"] == pytest.approx(-0.75)
    assert medium["Signal"] == "UNDERINDEX"
    assert bool(medium["Ready_For_Manual_Review"]) is True
    assert medium["Status"] == "READY_FOR_MANUAL_RESEARCH_REVIEW"
    assert medium["Recommended_Action"] == (
        "MANUAL_REVIEW_FROZEN_FORWARD_SIGNAL_ONLY_NO_PRODUCTION_CHANGE"
    )
    assert medium["Production_Authority"] == "NONE"
    assert bool(medium["No_Projection_Adjustment"]) is True
    assert bool(medium["Automatic_Decision_Allowed"]) is False


def test_forward_summary_remains_supporting_diagnostic_not_promotion_row() -> None:
    detail = _synthetic_forward_detail()
    evaluation = build_evaluation(detail)
    summary = build_summary(detail, evaluation).iloc[0]
    assert summary["Status"] == "READY_FOR_MANUAL_RESEARCH_REVIEW"
    assert summary["Rules_Preregistered"] == 3
    assert summary["Rules_Ready_For_Manual_Review"] == 1
    assert summary["Underindex_Rules"] == 1
    assert bool(summary["Supporting_Diagnostic_Only"]) is True
    assert bool(summary["Promotion_Row_Registered"]) is False
    assert bool(summary["No_Auto_Promotion"]) is True
    assert bool(summary["Automatic_Decision_Allowed"]) is False
    assert summary["Production_Authority"] == "NONE"


def test_historical_only_rows_cannot_grade_forward_protocol() -> None:
    history = pd.DataFrame(
        [
            _history_row(
                "2026-08-22",
                idx,
                residual=-3.0,
                confidence="MEDIUM",
                data_quality=40.0,
                leash="TIGHT",
            )
            for idx in range(30)
        ]
    )
    detail = build_forward_detail(history)
    assert detail.empty
    evaluation = build_evaluation(detail)
    assert evaluation["Future_Resolved_Starts"].eq(0).all()
    assert evaluation["Flagged_Starts"].eq(0).all()
    assert evaluation["Status"].eq("WAITING_FOR_FUTURE_DATA").all()
    assert evaluation["Ready_For_Manual_Review"].eq(False).all()
    summary = build_summary(detail, evaluation).iloc[0]
    assert summary["Status"] == "WAITING_FOR_FUTURE_DATA"
    assert summary["Future_Resolved_Starts"] == 0


def test_forward_contract_is_frozen_future_only_report_only() -> None:
    assert PREREGISTERED_GAME_DATE == "2026-08-22"
    assert FIRST_ELIGIBLE_GAME_DATE == "2026-08-23"
    assert MIN_GLOBAL_RESOLVED_STARTS == 60
    assert MIN_GLOBAL_RESOLVED_DAYS == 10
    assert MIN_GLOBAL_PITCHERS == 20
    assert MIN_RULE_STARTS == 15
    assert UNDERINDEX_RESIDUAL_LIFT == -0.50
    assert OVERINDEX_RESIDUAL_LIFT == 0.50
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert NO_PROJECTION_ADJUSTMENT is True
    assert NO_AUTO_PROMOTION is True
    assert AUTOMATIC_DECISION_ALLOWED is False
    assert SUPPORTING_DIAGNOSTIC_ONLY is True
    assert PROMOTION_ROW_REGISTERED is False
    assert VERSION == "projection-underperformer-forward-challenger-v1-preregistered-report-only"
