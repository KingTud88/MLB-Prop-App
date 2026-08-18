from __future__ import annotations

import pandas as pd

from training.opponent_matchup_weak_reduce_neutral_shadow import (
    DERIVATION_CUTOFF_DATE,
    FROZEN_DELTA_MAX_PP,
    FROZEN_DELTA_MIN_PP,
    PRODUCTION_AUTHORITY,
    build_detail,
    summarize,
)


def _row(
    *,
    game_date: str,
    opponent: str,
    delta_pp: float = -0.50,
    adjustment: float = -0.10,
    neutral: float = 5.0,
    actual: float = 5.0,
    idx: int = 1,
) -> dict[str, object]:
    return {
        "game_date": game_date,
        "game_pk": 900000 + idx,
        "pitcher_id": 700000 + idx,
        "player": f"Pitcher {idx}",
        "team": "AAA",
        "opponent": opponent,
        "Opponent_K_Rate": 0.219,
        "Opponent_K_Delta_PP": delta_pp,
        "Opponent_K_Extremity": "-0.25–0.99pp" if delta_pp > -1.0 else "-1.00–1.49pp",
        "Matchup_PA": 1800.0,
        "Matchup_PA_Band": "1,000–1,999 PA",
        "Matchup_Batters": 9.0,
        "Lineup_State": "CONFIRMED",
        "Data_Quality": 75,
        "Quality_Band": "70–79",
        "Neutral_Opponent_Projection": neutral,
        "Neutral_K_Projection_Level": "5.0–5.99 K",
        "Applied_Projection": neutral + adjustment,
        "Matchup_Adjustment_K": adjustment,
        "Reduction_Magnitude_K": abs(adjustment),
        "Reduction_Magnitude_Band": "0.10–0.24 K",
        "Actual_Strikeouts": actual,
    }


def test_only_frozen_weak_reduce_band_is_eligible() -> None:
    source = pd.DataFrame(
        [
            _row(game_date="2026-08-16", opponent="BOS", delta_pp=-0.50, idx=1),
            _row(game_date="2026-08-16", opponent="NYY", delta_pp=-1.20, adjustment=-0.15, idx=2),
            _row(game_date="2026-08-16", opponent="TOR", delta_pp=-0.10, adjustment=-0.02, idx=3),
            _row(game_date="2026-08-16", opponent="BAL", delta_pp=-0.25, adjustment=-0.05, idx=4),
        ]
    )
    detail = build_detail(source)

    assert len(detail) == 2
    assert set(detail["opponent"]) == {"BOS", "BAL"}
    assert detail["Weak_Reduce_Eligible"].all()
    assert detail["Opponent_K_Delta_PP"].gt(FROZEN_DELTA_MIN_PP).all()
    assert detail["Opponent_K_Delta_PP"].le(FROZEN_DELTA_MAX_PP).all()


def test_neutralization_uses_neutral_counterfactual_not_live_applied_projection() -> None:
    detail = build_detail(
        pd.DataFrame([
            _row(game_date="2026-08-16", opponent="BOS", neutral=5.2, adjustment=-0.08, actual=5.0)
        ])
    )
    row = detail.iloc[0]

    assert row["Applied_Projection"] == 5.12
    assert row["Neutralized_Projection"] == 5.2
    assert row["Production_Authority"] == PRODUCTION_AUTHORITY
    assert bool(row["Report_Only"]) is True


def test_cutoff_keeps_august_17_derivation_only_and_august_18_forward() -> None:
    assert DERIVATION_CUTOFF_DATE == "2026-08-17"
    detail = build_detail(
        pd.DataFrame(
            [
                _row(game_date="2026-08-17", opponent="BOS", idx=1),
                _row(game_date="2026-08-18", opponent="NYY", idx=2),
            ]
        )
    )

    lanes = dict(zip(detail["game_date"], detail["Evidence_Lane"]))
    assert lanes["2026-08-17"] == "DERIVATION_BACKTEST"
    assert lanes["2026-08-18"] == "FORWARD_OOS"


def test_derivation_rows_can_never_promote() -> None:
    source = pd.DataFrame(
        [
            _row(
                game_date=f"2026-08-{1 + (i % 17):02d}",
                opponent=f"OPP{i % 15}",
                neutral=5.0,
                adjustment=-0.10,
                actual=5.0,
                idx=i,
            )
            for i in range(60)
        ]
    )
    summary = summarize(build_detail(source))
    derivation = summary.loc[summary["Evidence_Lane"].eq("DERIVATION_BACKTEST")].iloc[0]

    assert derivation["Evidence_Status"] == "DESCRIPTIVE_ONLY"
    assert derivation["Recommended_Action"] == "FREEZE_HYPOTHESIS_AND_COLLECT_FORWARD_EVIDENCE"


def test_forward_sample_marks_supported_when_frozen_neutralization_clears_gates() -> None:
    rows = []
    for i in range(30):
        day = 18 + (i % 10)
        rows.append(
            _row(
                game_date=f"2026-08-{day:02d}",
                opponent=f"OPP{i % 12}",
                neutral=5.0,
                adjustment=-0.10,
                actual=5.0,
                idx=i,
            )
        )
    summary = summarize(build_detail(pd.DataFrame(rows)))
    forward = summary.loc[summary["Evidence_Lane"].eq("FORWARD_OOS")].iloc[0]

    assert forward["Starts"] == 30
    assert forward["Observed_Days"] == 10
    assert forward["Distinct_Opponents"] == 12
    assert forward["Evidence_Status"] == "SUPPORTED"
    assert forward["Neutralized_Relative_MAE_vs_Applied"] > 0.0
    assert forward["Neutralized_Win_Share_vs_Applied"] == 1.0
    assert forward["Production_Authority"] == "NONE"


def test_small_forward_sample_stays_learning() -> None:
    detail = build_detail(
        pd.DataFrame([
            _row(game_date="2026-08-18", opponent="BOS", actual=5.0)
        ])
    )
    summary = summarize(detail)
    forward = summary.loc[summary["Evidence_Lane"].eq("FORWARD_OOS")].iloc[0]

    assert forward["Evidence_Status"] == "LEARNING"
    assert forward["Production_Authority"] == "NONE"
