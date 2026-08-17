from __future__ import annotations

import pandas as pd

from training.opponent_matchup_reduce_stress import (
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    build_reduce_detail,
    build_segments,
    summarize,
)


def _scored_reduce_frame(
    n: int,
    *,
    days: int,
    opponents: int,
    applied_abs: float,
    neutral_abs: float,
    applied_error: float,
    neutral_error: float,
    applied_win: bool,
) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append({
            "game_date": f"2026-08-{1 + (i % days):02d}",
            "opponent": f"OPP{i % opponents:02d}",
            "Applied_Absolute_Error": applied_abs,
            "Neutral_Absolute_Error": neutral_abs,
            "Applied_Error": applied_error,
            "Neutral_Error": neutral_error,
            "Applied_Win": applied_win,
            "Neutral_Win": not applied_win,
            "Tie": False,
            "Applied_Underprediction": applied_error < 0,
            "Neutral_Underprediction": neutral_error < 0,
            "Reduction_Magnitude_K": 0.20,
            "Matchup_Adjustment_K": -0.20,
            "Opponent_K_Delta_PP": -1.8,
            "Matchup_PA": 1800,
            "Opponent_K_Extremity": "-1.50–2.49pp",
            "Reduction_Magnitude_Band": "0.10–0.24 K",
            "Lineup_State": "CONFIRMED",
            "Neutral_K_Projection_Level": "5.0–5.99 K",
            "Matchup_PA_Band": "1,000–1,999 PA",
            "Quality_Band": "70–79",
        })
    return pd.DataFrame(rows)


def test_build_reduce_detail_filters_and_labels_suppressive_rows() -> None:
    source = pd.DataFrame([
        {
            "game_date": "2026-08-17", "game_pk": 1, "pitcher_id": 10,
            "player": "A", "team": "AAA", "opponent": "BBB",
            "Auditable": True, "Adjustment_Direction": "REDUCE",
            "Opponent_K_Rate": 0.19, "Opponent_K_Delta_PP": -2.7,
            "Matchup_PA": 2200, "Matchup_Batters": 9, "Lineup_State": "CONFIRMED",
            "Data_Quality": 74, "Quality_Band": "70–79",
            "Neutral_Opponent_Projection": 5.4, "Applied_Projection": 5.05,
            "Matchup_Adjustment_K": -0.35, "Actual_Strikeouts": 6,
            "Applied_Absolute_Error": 0.95, "Neutral_Absolute_Error": 0.60,
            "Applied_Error": -0.95, "Neutral_Error": -0.60,
            "Applied_Win": False, "Neutral_Win": True, "Tie": False,
        },
        {
            "game_date": "2026-08-17", "game_pk": 2, "pitcher_id": 11,
            "player": "B", "team": "AAA", "opponent": "CCC",
            "Auditable": True, "Adjustment_Direction": "BOOST",
            "Opponent_K_Delta_PP": 2.0, "Matchup_Adjustment_K": 0.2,
        },
        {
            "game_date": "2026-08-17", "game_pk": 3, "pitcher_id": 12,
            "player": "C", "team": "AAA", "opponent": "DDD",
            "Auditable": False, "Adjustment_Direction": "REDUCE",
            "Opponent_K_Delta_PP": -1.0, "Matchup_Adjustment_K": -0.1,
        },
    ])

    detail = build_reduce_detail(source)
    assert len(detail) == 1
    row = detail.iloc[0]
    assert row["Opponent_K_Extremity"] == "-2.50pp+"
    assert row["Reduction_Magnitude_Band"] == "0.25–0.39 K"
    assert row["Neutral_K_Projection_Level"] == "5.0–5.99 K"
    assert row["Matchup_PA_Band"] == "2,000–2,999 PA"
    assert bool(row["Applied_Underprediction"])
    assert bool(row["Neutral_Underprediction"])
    assert bool(row["Report_Only"]) is REPORT_ONLY
    assert row["Production_Authority"] == PRODUCTION_AUTHORITY


def test_gate_waits_for_time_diversity_even_when_early_read_supported() -> None:
    detail = _scored_reduce_frame(
        80, days=5, opponents=25, applied_abs=1.8, neutral_abs=2.0,
        applied_error=0.1, neutral_error=0.2, applied_win=True,
    )
    summary = summarize(detail).iloc[0]
    assert summary["Finding"] == "INCONCLUSIVE"
    assert summary["Early_Read"] == "LEAN_SUPPORTED"
    assert summary["Recommended_Action"] == "KEEP_CURRENT_REDUCTION_AND_LEARN"
    assert not bool(summary["Manual_Review_Ready"])


def test_gate_supports_reduction_after_size_time_and_diversity_clear() -> None:
    detail = _scored_reduce_frame(
        75, days=10, opponents=15, applied_abs=1.8, neutral_abs=2.0,
        applied_error=0.1, neutral_error=0.2, applied_win=True,
    )
    summary = summarize(detail).iloc[0]
    assert summary["Finding"] == "SUPPORTED"
    assert summary["Recommended_Action"] == "KEEP_CURRENT_REDUCTION"
    assert bool(summary["Manual_Review_Ready"])


def test_gate_flags_too_aggressive_when_reduction_hurts() -> None:
    detail = _scored_reduce_frame(
        75, days=10, opponents=15, applied_abs=2.2, neutral_abs=2.0,
        applied_error=-0.35, neutral_error=-0.10, applied_win=False,
    )
    summary = summarize(detail).iloc[0]
    assert summary["Finding"] == "TOO AGGRESSIVE"
    assert summary["Early_Read"] == "LEAN_TOO_AGGRESSIVE"
    assert bool(summary["Manual_Review_Ready"])


def test_segments_cover_all_requested_robustness_dimensions() -> None:
    detail = _scored_reduce_frame(
        10, days=5, opponents=5, applied_abs=1.8, neutral_abs=2.0,
        applied_error=0.1, neutral_error=0.2, applied_win=True,
    )
    segments = build_segments(detail)
    assert set(segments["Dimension"]) == {
        "OVERALL", "OPPONENT K EXTREMITY", "REDUCTION MAGNITUDE", "LINEUP STATE",
        "NEUTRAL K PROJECTION LEVEL", "MATCHUP PA", "QUALITY BAND",
    }
    overall = segments.loc[segments["Dimension"].eq("OVERALL")].iloc[0]
    assert overall["Stress_Read"] == "HELPING"
