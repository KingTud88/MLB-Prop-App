from __future__ import annotations

import math

import pandas as pd

from training.opponent_matchup_validation import (
    LEAGUE_K_RATE,
    MIN_EVAL_STARTS,
    build_detail,
    build_segments,
    evaluate_gate,
    neutral_opponent_projection,
)


def _row(
    day: int,
    *,
    opponent: str | None = None,
    opponent_k_pct: float = 25.0,
    projection: float = 6.0,
    actual: float = 6.0,
    capture_offset_hours: float = -6.0,
    resolved_offset_hours: float = 4.0,
    lineup_confirmed: bool = False,
) -> dict[str, object]:
    game_time = pd.Timestamp("2026-06-01T23:00:00Z") + pd.Timedelta(days=day)
    return {
        "game_date": game_time.date().isoformat(),
        "game_pk": 800000 + day,
        "pitcher_id": 600000 + day,
        "player": f"Pitcher {day}",
        "team": "CLE",
        "opponent": opponent or f"OPP{day % 30:02d}",
        "game_time": game_time.isoformat(),
        "captured_at_utc": (game_time + pd.Timedelta(hours=capture_offset_hours)).isoformat(),
        "resolved_at_utc": (game_time + pd.Timedelta(hours=resolved_offset_hours)).isoformat(),
        "projection": projection,
        "actual_strikeouts": actual,
        "opponent_k_pct": opponent_k_pct,
        "matchup_pa": 250,
        "matchup_batters": 9,
        "lineup_confirmed": lineup_confirmed,
        "data_quality": 82,
    }


def test_percent_and_decimal_k_rates_produce_same_neutral_counterfactual() -> None:
    a = build_detail(pd.DataFrame([_row(0, opponent_k_pct=25.0)])).iloc[0]
    b = build_detail(pd.DataFrame([_row(0, opponent_k_pct=0.25)])).iloc[0]
    assert math.isclose(float(a["Opponent_K_Rate"]), 0.25)
    assert math.isclose(float(a["Neutral_Opponent_Projection"]), float(b["Neutral_Opponent_Projection"]), rel_tol=1e-12)


def test_counterfactual_uses_only_projection_and_frozen_opponent_rate() -> None:
    first = build_detail(pd.DataFrame([_row(0, actual=2.0)])).iloc[0]
    second = build_detail(pd.DataFrame([_row(0, actual=10.0)])).iloc[0]
    assert math.isclose(float(first["Neutral_Opponent_Projection"]), float(second["Neutral_Opponent_Projection"]), rel_tol=1e-12)
    expected = neutral_opponent_projection(6.0, 0.25)
    assert math.isclose(float(first["Neutral_Opponent_Projection"]), expected, rel_tol=1e-12)


def test_high_k_opponent_boosts_applied_projection_relative_to_neutral() -> None:
    row = build_detail(pd.DataFrame([_row(0, opponent_k_pct=25.0)])).iloc[0]
    assert row["Adjustment_Direction"] == "BOOST"
    assert float(row["Applied_Projection"]) > float(row["Neutral_Opponent_Projection"])
    assert bool(row["Informative_Adjustment"]) is True


def test_low_k_opponent_reduces_applied_projection_relative_to_neutral() -> None:
    row = build_detail(pd.DataFrame([_row(0, opponent_k_pct=19.5)])).iloc[0]
    assert row["Adjustment_Direction"] == "REDUCE"
    assert float(row["Applied_Projection"]) < float(row["Neutral_Opponent_Projection"])


def test_league_neutral_rows_do_not_pad_auditable_sample() -> None:
    row = build_detail(pd.DataFrame([_row(0, opponent_k_pct=LEAGUE_K_RATE * 100.0)])).iloc[0]
    assert bool(row["Informative_Adjustment"]) is False
    assert bool(row["Auditable"]) is False


def test_post_start_capture_is_never_auditable() -> None:
    row = build_detail(pd.DataFrame([_row(0, capture_offset_hours=1.0)])).iloc[0]
    assert row["Lineage"] == "POST_START_CAPTURE"
    assert bool(row["Auditable"]) is False


def test_large_positive_synthetic_sample_can_reach_strong_but_has_no_authority() -> None:
    rows = [
        _row(
            i,
            opponent=f"OPP{i % 26:02d}",
            opponent_k_pct=25.0,
            projection=6.0,
            actual=6.0,
            lineup_confirmed=(i % 2 == 0),
        )
        for i in range(170)
    ]
    gate = evaluate_gate(build_detail(pd.DataFrame(rows))).iloc[0]
    assert gate["Evidence_Status"] == "STRONG EVIDENCE"
    assert bool(gate["Manual_Review_Ready"]) is True
    assert gate["Recommended_Action"] == "MANUAL_REVIEW_READY"
    assert gate["Production_Authority"] == "NONE"
    assert bool(gate["Report_Only"]) is True


def test_large_negative_synthetic_sample_returns_caution() -> None:
    neutral = neutral_opponent_projection(6.0, 0.25)
    rows = [
        _row(
            i,
            opponent=f"OPP{i % 20:02d}",
            opponent_k_pct=25.0,
            projection=6.0,
            actual=neutral,
        )
        for i in range(max(MIN_EVAL_STARTS + 10, 80))
    ]
    gate = evaluate_gate(build_detail(pd.DataFrame(rows))).iloc[0]
    assert gate["Evidence_Status"] == "CAUTION"
    assert gate["Production_Authority"] == "NONE"


def test_segments_include_matchup_adjustment_lineup_and_quality_views() -> None:
    detail = build_detail(pd.DataFrame([
        _row(0, opponent_k_pct=25.0, lineup_confirmed=True),
        _row(1, opponent_k_pct=19.5, lineup_confirmed=False),
    ]))
    segments = build_segments(detail)
    dimensions = set(segments["Dimension"])
    assert "MATCHUP ENVIRONMENT" in dimensions
    assert "ADJUSTMENT DIRECTION" in dimensions
    assert "ADJUSTMENT MAGNITUDE" in dimensions
    assert "LINEUP STATE" in dimensions
    assert "QUALITY BAND" in dimensions
    assert set(segments["Production_Authority"]) == {"NONE"}
