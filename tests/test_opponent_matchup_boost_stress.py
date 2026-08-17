from __future__ import annotations

import math

import pandas as pd

from training.opponent_matchup_boost_stress import (
    MIN_BOOST_DAYS,
    MIN_BOOST_OPPONENTS,
    MIN_BOOST_STARTS,
    build_boost_detail,
    build_segments,
    evaluate_gate,
)
from training.opponent_matchup_validation import build_detail, neutral_opponent_projection


def _row(
    i: int,
    *,
    day: int | None = None,
    opponent: str | None = None,
    opponent_k_pct: float = 25.0,
    projection: float = 6.0,
    actual: float = 6.0,
    lineup_confirmed: bool = True,
    matchup_pa: float = 1800.0,
    data_quality: float = 78.0,
) -> dict[str, object]:
    day = i if day is None else day
    game_time = pd.Timestamp("2026-06-01T23:00:00Z") + pd.Timedelta(days=day)
    return {
        "game_date": game_time.date().isoformat(),
        "game_pk": 900000 + i,
        "pitcher_id": 700000 + i,
        "player": f"Pitcher {i}",
        "team": "CLE",
        "opponent": opponent or f"OPP{i % 20:02d}",
        "game_time": game_time.isoformat(),
        "captured_at_utc": (game_time - pd.Timedelta(hours=5)).isoformat(),
        "resolved_at_utc": (game_time + pd.Timedelta(hours=4)).isoformat(),
        "projection": projection,
        "actual_strikeouts": actual,
        "opponent_k_pct": opponent_k_pct,
        "matchup_pa": matchup_pa,
        "matchup_batters": 9,
        "lineup_confirmed": lineup_confirmed,
        "data_quality": data_quality,
    }


def _boost_detail(rows: list[dict[str, object]]) -> pd.DataFrame:
    return build_boost_detail(build_detail(pd.DataFrame(rows)))


def test_stress_detail_keeps_only_auditable_positive_boosts() -> None:
    rows = [
        _row(0, opponent_k_pct=25.0),
        _row(1, opponent_k_pct=19.5),
        _row(2, opponent_k_pct=22.4),
    ]
    boost = _boost_detail(rows)
    assert len(boost) == 1
    assert boost.iloc[0]["Opponent_K_Delta_PP"] > 0
    assert boost.iloc[0]["Matchup_Adjustment_K"] > 0
    assert boost.iloc[0]["Production_Authority"] == "NONE"
    assert bool(boost.iloc[0]["Report_Only"]) is True


def test_segmentation_is_pregame_safe_and_does_not_depend_on_final_outcome() -> None:
    first = _boost_detail([_row(0, actual=2.0)]).iloc[0]
    second = _boost_detail([_row(0, actual=10.0)]).iloc[0]
    for column in (
        "Opponent_K_Extremity",
        "Boost_Magnitude_Band",
        "Neutral_K_Projection_Level",
        "Matchup_PA_Band",
        "Lineup_State",
        "Quality_Band",
    ):
        assert first[column] == second[column]
    assert math.isclose(
        float(first["Neutral_Opponent_Projection"]),
        float(second["Neutral_Opponent_Projection"]),
        rel_tol=1e-12,
    )


def test_small_time_sample_stays_formally_inconclusive() -> None:
    rows = [
        _row(
            i,
            day=i % max(1, MIN_BOOST_DAYS - 1),
            opponent=f"OPP{i % max(MIN_BOOST_OPPONENTS, 15):02d}",
            actual=6.0,
        )
        for i in range(MIN_BOOST_STARTS + 10)
    ]
    gate = evaluate_gate(_boost_detail(rows)).iloc[0]
    assert gate["Finding"] == "INCONCLUSIVE"
    assert gate["Recommended_Action"] == "KEEP_CURRENT_BOOST_AND_LEARN"
    assert gate["Production_Authority"] == "NONE"


def test_large_positive_sample_can_mark_boost_supported_without_authority() -> None:
    days = max(MIN_BOOST_DAYS + 2, 12)
    opponents = max(MIN_BOOST_OPPONENTS + 3, 15)
    rows = [
        _row(
            i,
            day=i % days,
            opponent=f"OPP{i % opponents:02d}",
            projection=6.0,
            actual=6.0,
        )
        for i in range(MIN_BOOST_STARTS + 25)
    ]
    gate = evaluate_gate(_boost_detail(rows)).iloc[0]
    assert gate["Finding"] == "SUPPORTED"
    assert gate["Early_Read"] == "LEAN_SUPPORTED"
    assert bool(gate["Manual_Review_Ready"]) is True
    assert gate["Production_Authority"] == "NONE"


def test_large_neutral_truth_sample_marks_positive_boost_too_hot() -> None:
    days = max(MIN_BOOST_DAYS + 2, 12)
    opponents = max(MIN_BOOST_OPPONENTS + 3, 15)
    neutral = neutral_opponent_projection(6.0, 0.25)
    rows = [
        _row(
            i,
            day=i % days,
            opponent=f"OPP{i % opponents:02d}",
            projection=6.0,
            actual=neutral,
        )
        for i in range(MIN_BOOST_STARTS + 25)
    ]
    gate = evaluate_gate(_boost_detail(rows)).iloc[0]
    assert gate["Finding"] == "TOO HOT"
    assert gate["Early_Read"] == "LEAN_TOO_HOT"
    assert gate["Recommended_Action"] == "MANUAL_REVIEW_DO_NOT_RETUNE_AUTOMATICALLY"
    assert gate["Production_Authority"] == "NONE"


def test_segments_cover_requested_boost_stress_dimensions() -> None:
    boost = _boost_detail([
        _row(0, opponent_k_pct=23.5, matchup_pa=700, data_quality=65),
        _row(1, opponent_k_pct=25.5, matchup_pa=2400, data_quality=78),
        _row(2, opponent_k_pct=27.0, matchup_pa=3300, data_quality=55),
    ])
    segments = build_segments(boost)
    dimensions = set(segments["Dimension"])
    assert {
        "OPPONENT K EXTREMITY",
        "BOOST MAGNITUDE",
        "LINEUP STATE",
        "NEUTRAL K PROJECTION LEVEL",
        "MATCHUP PA",
        "QUALITY BAND",
    }.issubset(dimensions)
    assert set(segments["Production_Authority"]) == {"NONE"}
