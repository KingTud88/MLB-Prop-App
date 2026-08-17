from __future__ import annotations

import pandas as pd

from training.opponent_matchup_boost_cap_shadow import (
    DERIVATION_CUTOFF_DATE,
    FROZEN_CAP_K,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    build_detail,
    summarize,
)


def _rows() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "game_date": "2026-08-16",
            "game_pk": 1,
            "pitcher_id": 10,
            "player": "Derivation",
            "team": "AAA",
            "opponent": "BBB",
            "Neutral_Opponent_Projection": 5.0,
            "Applied_Projection": 5.30,
            "Matchup_Adjustment_K": 0.30,
            "Actual_Strikeouts": 5.0,
        },
        {
            "game_date": "2026-08-17",
            "game_pk": 2,
            "pitcher_id": 11,
            "player": "Forward",
            "team": "CCC",
            "opponent": "DDD",
            "Neutral_Opponent_Projection": 4.0,
            "Applied_Projection": 4.08,
            "Matchup_Adjustment_K": 0.08,
            "Actual_Strikeouts": 4.0,
        },
    ])


def test_cap_is_frozen_and_only_reduces_large_positive_boosts() -> None:
    detail = build_detail(_rows())
    derivation = detail.iloc[0]
    forward = detail.iloc[1]

    assert FROZEN_CAP_K == 0.10
    assert derivation["Capped_Adjustment_K"] == 0.10
    assert derivation["Capped_Projection"] == 5.10
    assert bool(derivation["Cap_Was_Binding"]) is True
    assert forward["Capped_Adjustment_K"] == 0.08
    assert forward["Capped_Projection"] == 4.08
    assert bool(forward["Cap_Was_Binding"]) is False


def test_derivation_rows_never_count_as_forward_promotion_evidence() -> None:
    detail = build_detail(_rows())
    assert DERIVATION_CUTOFF_DATE == "2026-08-16"
    assert detail.iloc[0]["Evidence_Lane"] == "DERIVATION_BACKTEST"
    assert bool(detail.iloc[0]["Counts_For_Promotion"]) is False
    assert detail.iloc[1]["Evidence_Lane"] == "FORWARD_OOS"
    assert bool(detail.iloc[1]["Counts_For_Promotion"]) is True


def test_summary_is_report_only_and_forward_lane_stays_learning_when_small() -> None:
    summary = summarize(build_detail(_rows()))
    derivation = summary.loc[summary["Evidence_Lane"].eq("DERIVATION_BACKTEST")].iloc[0]
    forward = summary.loc[summary["Evidence_Lane"].eq("FORWARD_OOS")].iloc[0]

    assert derivation["Evidence_Status"] == "DESCRIPTIVE_ONLY"
    assert forward["Evidence_Status"] == "LEARNING"
    assert int(forward["Starts"]) == 1
    assert bool(forward["Report_Only"]) is REPORT_ONLY
    assert forward["Production_Authority"] == PRODUCTION_AUTHORITY == "NONE"
