from __future__ import annotations

import pandas as pd

from engine.starter_history import HISTORY_SEMANTICS
from training.top_plays_postmortem import (
    PRODUCTION_AUTHORITY,
    build_daily_combo_summary,
    build_segment_summary,
    overlay_persisted_active_lines,
    replay_real_line_top5,
)


def test_line_overlay_accepts_only_persisted_real_sources_and_manual_wins() -> None:
    history = pd.DataFrame({
        "game_pk": [1, 2, 3],
        "pitcher_id": [11, 22, 33],
    })
    archive = pd.DataFrame({
        "game_pk": [1, 2, 3],
        "pitcher_id": [11, 22, 33],
        "manual_strikeout_line": [5.5, pd.NA, pd.NA],
        "active_strikeout_line": [9.5, 6.5, 4.5],
        "active_strikeout_line_source": ["MODEL GRID · DIAGNOSTIC ONLY", "SAVED ODDS API", "MODEL GRID · DIAGNOSTIC ONLY"],
    })
    out = overlay_persisted_active_lines(history, archive)
    assert float(out.loc[0, "active_strikeout_line"]) == 5.5
    assert out.loc[0, "active_strikeout_line_source"] == "MANUAL"
    assert float(out.loc[1, "active_strikeout_line"]) == 6.5
    assert out.loc[1, "active_strikeout_line_source"] == "SAVED ODDS API"
    assert pd.isna(out.loc[2, "active_strikeout_line"])
    assert out.loc[2, "active_strikeout_line_source"] == ""


def test_real_line_replay_grades_a_frozen_manual_k_leg() -> None:
    history = pd.DataFrame([{
        "game_pk": 100,
        "game_date": "2026-08-10",
        "pitcher_id": 55,
        "player": "Test Pitcher",
        "team": "AAA",
        "opponent": "BBB",
        "projection": 6.2,
        "data_quality": 80,
        "starter_history_games": 8,
        "history_semantics": HISTORY_SEMANTICS,
        "sim_6p": 0.70,
        "math_6p": 0.70,
        "actual_strikeouts": 7,
        "lineup_confirmed": True,
        "lineup_source": "MLB_CONFIRMED",
        "weather_delay_risk": "NONE",
    }])
    archive = pd.DataFrame([{
        "game_pk": 100,
        "pitcher_id": 55,
        "manual_strikeout_line": 5.5,
    }])
    detail = replay_real_line_top5(history, archive)
    assert len(detail) == 1
    row = detail.iloc[0]
    assert row["Rank"] == 1
    assert row["Market"] == "Strikeouts"
    assert row["Side"] == "OVER"
    assert row["Line"] == 5.5
    assert row["Line Source"] == "MANUAL"
    assert bool(row["Hit"]) is True
    assert row["Lineup State"] == "CONFIRMED"
    assert row["Weather Risk"] == "NONE"
    assert row["Production Authority"] == PRODUCTION_AUTHORITY == "NONE"


def test_segment_summary_breaks_out_rank_market_and_line_source() -> None:
    detail = pd.DataFrame([
        {"Rank": 1, "Market": "Strikeouts", "Side": "OVER", "Status": "MODEL PLAY", "Probability Band": "60–64%", "Quality Band": "80–89", "Line Source": "MANUAL", "Lineup State": "CONFIRMED", "Weather Risk": "NONE", "Historical Market Health": "LEARNING", "Model Probability": 0.62, "Projection Margin": 0.8, "Outcome Margin": 1.5, "Hit": True},
        {"Rank": 2, "Market": "Total Outs", "Side": "UNDER", "Status": "WATCH", "Probability Band": "55–59%", "Quality Band": "70–79", "Line Source": "SAVED ODDS API", "Lineup State": "PROJECTED", "Weather Risk": "LOW", "Historical Market Health": "LEARNING", "Model Probability": 0.57, "Projection Margin": 0.6, "Outcome Margin": -0.5, "Hit": False},
    ])
    report = build_segment_summary(detail)
    assert ((report["Dimension"] == "OVERALL") & (report["Segment"] == "ALL REAL-LINE TOP PLAYS")).any()
    assert ((report["Dimension"] == "RANK") & (report["Segment"] == "1")).any()
    assert ((report["Dimension"] == "MARKET") & (report["Segment"] == "Strikeouts")).any()
    assert ((report["Dimension"] == "LINE SOURCE") & (report["Segment"] == "MANUAL")).any()
    overall = report.loc[report["Dimension"].eq("OVERALL")].iloc[0]
    assert overall["Settled Legs"] == 2
    assert overall["Hit Rate"] == 0.5


def test_daily_combo_summary_requires_complete_rank_prefix() -> None:
    detail = pd.DataFrame([
        {"Postmortem Date": "2026-08-10", "Rank": 1, "Hit": True},
        {"Postmortem Date": "2026-08-10", "Rank": 2, "Hit": True},
        {"Postmortem Date": "2026-08-10", "Rank": 3, "Hit": False},
        {"Postmortem Date": "2026-08-11", "Rank": 1, "Hit": True},
        {"Postmortem Date": "2026-08-11", "Rank": 3, "Hit": True},
    ])
    daily = build_daily_combo_summary(detail).set_index("Date")
    assert bool(daily.loc["2026-08-10", "Top 2 All Hit"]) is True
    assert bool(daily.loc["2026-08-10", "Top 3 All Hit"]) is False
    assert pd.isna(daily.loc["2026-08-10", "Top 5 All Hit"])
    assert pd.isna(daily.loc["2026-08-11", "Top 2 All Hit"])
