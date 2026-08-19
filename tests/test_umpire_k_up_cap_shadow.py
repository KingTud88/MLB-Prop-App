from __future__ import annotations

import pandas as pd
import pytest

from training.umpire_k_up_cap_shadow import (
    DERIVATION_CUTOFF_DATE,
    FROZEN_MAX_K_UP_FACTOR,
    NO_PROJECTION_ADJUSTMENT,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    build_detail,
    summarize,
)


def _rows() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "game_date": "2026-08-18",
            "game_pk": 1,
            "pitcher_id": 10,
            "player": "Derivation Up",
            "team": "AAA",
            "opponent": "BBB",
            "umpire_id": 100,
            "umpire_name": "Blue One",
            "OOS_Eligible": True,
            "Base_Projection": 5.0,
            "Candidate_Factor": 1.04,
            "Candidate_Projection": 5.20,
            "Actual_Strikeouts": 5.0,
        },
        {
            "game_date": "2026-08-19",
            "game_pk": 2,
            "pitcher_id": 11,
            "player": "Forward Small Up",
            "team": "CCC",
            "opponent": "DDD",
            "umpire_id": 101,
            "umpire_name": "Blue Two",
            "OOS_Eligible": True,
            "Base_Projection": 4.0,
            "Candidate_Factor": 1.01,
            "Candidate_Projection": 4.04,
            "Actual_Strikeouts": 4.0,
        },
        {
            "game_date": "2026-08-19",
            "game_pk": 3,
            "pitcher_id": 12,
            "player": "Forward Down",
            "team": "EEE",
            "opponent": "FFF",
            "umpire_id": 102,
            "umpire_name": "Blue Three",
            "OOS_Eligible": True,
            "Base_Projection": 6.0,
            "Candidate_Factor": 0.97,
            "Candidate_Projection": 5.82,
            "Actual_Strikeouts": 6.0,
        },
        {
            "game_date": "2026-08-19",
            "game_pk": 4,
            "pitcher_id": 13,
            "player": "Forward Large Up",
            "team": "GGG",
            "opponent": "HHH",
            "umpire_id": 103,
            "umpire_name": "Blue Four",
            "OOS_Eligible": True,
            "Base_Projection": 5.0,
            "Candidate_Factor": 1.05,
            "Candidate_Projection": 5.25,
            "Actual_Strikeouts": 5.0,
        },
    ])


def test_cap_only_changes_k_up_factors_above_one_point_five_percent() -> None:
    detail = build_detail(_rows())

    derivation = detail.loc[detail["game_pk"].eq(1)].iloc[0]
    small_up = detail.loc[detail["game_pk"].eq(2)].iloc[0]
    down = detail.loc[detail["game_pk"].eq(3)].iloc[0]
    large_up = detail.loc[detail["game_pk"].eq(4)].iloc[0]

    assert FROZEN_MAX_K_UP_FACTOR == 1.015
    assert derivation["Capped_Factor"] == 1.015
    assert bool(derivation["Cap_Was_Binding"]) is True
    assert small_up["Capped_Factor"] == 1.01
    assert bool(small_up["Cap_Was_Binding"]) is False
    assert down["Capped_Factor"] == 0.97
    assert bool(down["Cap_Was_Binding"]) is False
    assert large_up["Capped_Factor"] == 1.015
    assert large_up["Capped_Projection"] == pytest.approx(5.075)
    assert bool(large_up["Cap_Was_Binding"]) is True


def test_only_forward_binding_rows_count_for_promotion_evidence() -> None:
    detail = build_detail(_rows())

    derivation = detail.loc[detail["game_pk"].eq(1)].iloc[0]
    small_up = detail.loc[detail["game_pk"].eq(2)].iloc[0]
    down = detail.loc[detail["game_pk"].eq(3)].iloc[0]
    large_up = detail.loc[detail["game_pk"].eq(4)].iloc[0]

    assert DERIVATION_CUTOFF_DATE == "2026-08-18"
    assert derivation["Evidence_Lane"] == "DERIVATION_BACKTEST"
    assert bool(derivation["Counts_For_Promotion"]) is False
    assert small_up["Evidence_Lane"] == "FORWARD_OOS"
    assert bool(small_up["Counts_For_Promotion"]) is False
    assert bool(down["Counts_For_Promotion"]) is False
    assert bool(large_up["Counts_For_Promotion"]) is True


def test_forward_summary_stays_learning_when_changed_sample_is_small() -> None:
    summary = summarize(build_detail(_rows()))
    derivation = summary.loc[summary["Evidence_Lane"].eq("DERIVATION_BACKTEST")].iloc[0]
    forward = summary.loc[summary["Evidence_Lane"].eq("FORWARD_OOS")].iloc[0]

    assert derivation["Evidence_Status"] == "DESCRIPTIVE_ONLY"
    assert forward["Evidence_Status"] == "LEARNING"
    assert int(forward["Eligible_Starts"]) == 3
    assert int(forward["Changed_Starts"]) == 1
    assert bool(forward["Report_Only"]) is REPORT_ONLY
    assert forward["Production_Authority"] == PRODUCTION_AUTHORITY == "NONE"
    assert bool(forward["No_Projection_Adjustment"]) is NO_PROJECTION_ADJUSTMENT


def test_large_forward_sample_can_support_frozen_cap_without_auto_promotion() -> None:
    rows = []
    for i in range(36):
        day = 19 + (i % 12)
        rows.append({
            "game_date": f"2026-08-{day:02d}",
            "game_pk": 1000 + i,
            "pitcher_id": 2000 + i,
            "player": f"P{i}",
            "team": "AAA",
            "opponent": f"O{i % 15}",
            "umpire_id": 3000 + (i % 12),
            "umpire_name": f"U{i % 12}",
            "OOS_Eligible": True,
            "Base_Projection": 5.0,
            "Candidate_Factor": 1.05,
            "Candidate_Projection": 5.25,
            "Actual_Strikeouts": 5.0,
        })

    summary = summarize(build_detail(pd.DataFrame(rows)))
    forward = summary.loc[summary["Evidence_Lane"].eq("FORWARD_OOS")].iloc[0]

    assert forward["Evidence_Status"] == "SUPPORTED"
    assert bool(forward["Manual_Review_Ready"]) is True
    assert forward["Recommended_Action"] == "MANUAL_RESEARCH_REVIEW_ONLY"
    assert forward["Production_Authority"] == "NONE"
