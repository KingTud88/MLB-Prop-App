import pandas as pd

from engine.projection_crushers import (
    bettable_k_label,
    bettable_k_result,
    bettable_k_target,
    crusher_report,
    directional_k_result,
    underperformer_report,
)
from engine.starter_history import HISTORY_SEMANTICS


def test_bettable_k_target_floors_projection_to_supported_ladder():
    assert bettable_k_target(5.07) == 5
    assert bettable_k_target(5.99) == 5
    assert bettable_k_target(6.00) == 6
    assert bettable_k_target(4.60) == 4
    assert bettable_k_target(12.80) == 12
    assert bettable_k_target(2.99) is None
    assert bettable_k_label(5.07) == "5+"
    assert bettable_k_label(2.99) == "—"


def test_ladder_result_and_exact_projection_result_are_separate_questions():
    # Model-supported ladder: 5.07 -> 5+, so exactly 5 Ks clears the ladder target.
    assert bettable_k_result(5.07, 5) == "✅ WIN"
    assert bettable_k_result(4.60, 10) == "✅ WIN"
    assert bettable_k_result(4.60, 4) == "✅ WIN"
    assert bettable_k_result(4.60, 3) == "❌ MISS"
    assert bettable_k_result(5.99, 5) == "✅ WIN"
    assert bettable_k_result(6.00, 5) == "❌ MISS"
    assert bettable_k_result(2.99, 8) == "NO CALL"
    assert bettable_k_result(5.07, None) == "PENDING"

    # Projection Crusher research uses the exact frozen projection, not floor(projection).
    assert directional_k_result(5.07, 5) == "❌ MISS"
    assert directional_k_result(5.07, 6) == "✅ WIN"
    assert directional_k_result(5.00, 5) == "❌ MISS"
    assert directional_k_result(5.00, 6) == "✅ WIN"
    assert directional_k_result(None, 6) == "PENDING"


def test_crusher_report_rewards_repeat_exact_projection_beats():
    frame = pd.DataFrame([
        {"pitcher_id": 1, "player": "Pitcher A", "game_date": "2026-08-01", "captured_at_utc": "2026-08-01T12:00:00Z", "projection": 5.2, "actual_strikeouts": 7, "history_semantics": HISTORY_SEMANTICS},
        {"pitcher_id": 1, "player": "Pitcher A", "game_date": "2026-08-06", "captured_at_utc": "2026-08-06T12:00:00Z", "projection": 4.8, "actual_strikeouts": 8, "history_semantics": HISTORY_SEMANTICS},
        {"pitcher_id": 1, "player": "Pitcher A", "game_date": "2026-08-11", "captured_at_utc": "2026-08-11T12:00:00Z", "projection": 4.6, "actual_strikeouts": 10, "history_semantics": HISTORY_SEMANTICS},
        {"pitcher_id": 2, "player": "Pitcher B", "game_date": "2026-08-02", "captured_at_utc": "2026-08-02T12:00:00Z", "projection": 5.5, "actual_strikeouts": 4, "history_semantics": HISTORY_SEMANTICS},
        {"pitcher_id": 2, "player": "Pitcher B", "game_date": "2026-08-07", "captured_at_utc": "2026-08-07T12:00:00Z", "projection": 5.0, "actual_strikeouts": 5, "history_semantics": HISTORY_SEMANTICS},
        {"pitcher_id": 2, "player": "Pitcher B", "game_date": "2026-08-12", "captured_at_utc": "2026-08-12T12:00:00Z", "projection": 4.5, "actual_strikeouts": 6, "history_semantics": HISTORY_SEMANTICS},
    ])
    report = crusher_report(frame)
    row = report.loc[report["Pitcher"].eq("Pitcher A")].iloc[0]
    assert row["Projection Wins"] == 3
    assert row["Win Rate"] == 1.0
    assert row["Current Win Streak"] == 3
    assert row["2+ K Crushes"] == 2
    assert row["Avg K vs Projection"] > 0.5
    assert row["Crusher Status"] == "🔥 CRUSHER"

    row_b = report.loc[report["Pitcher"].eq("Pitcher B")].iloc[0]
    assert row_b["Projection Wins"] == 1
    assert row_b["Win Rate"] == 1 / 3
    # 5 actual Ks at an exact 5.0 projection is not an exact-projection win.
    assert row_b["Current Win Streak"] == 1


def test_underperformer_report_flags_repeat_negative_exact_projection_residuals():
    frame = pd.DataFrame([
        {"pitcher_id": 7, "player": "Pitcher Low", "game_date": "2026-08-01", "captured_at_utc": "2026-08-01T12:00:00Z", "projection": 7.2, "actual_strikeouts": 4, "history_semantics": HISTORY_SEMANTICS},
        {"pitcher_id": 7, "player": "Pitcher Low", "game_date": "2026-08-06", "captured_at_utc": "2026-08-06T12:00:00Z", "projection": 6.8, "actual_strikeouts": 5, "history_semantics": HISTORY_SEMANTICS},
        {"pitcher_id": 7, "player": "Pitcher Low", "game_date": "2026-08-11", "captured_at_utc": "2026-08-11T12:00:00Z", "projection": 6.5, "actual_strikeouts": 3, "history_semantics": HISTORY_SEMANTICS},
        {"pitcher_id": 8, "player": "Pitcher Mixed", "game_date": "2026-08-02", "captured_at_utc": "2026-08-02T12:00:00Z", "projection": 5.5, "actual_strikeouts": 4, "history_semantics": HISTORY_SEMANTICS},
        {"pitcher_id": 8, "player": "Pitcher Mixed", "game_date": "2026-08-07", "captured_at_utc": "2026-08-07T12:00:00Z", "projection": 5.0, "actual_strikeouts": 5, "history_semantics": HISTORY_SEMANTICS},
        {"pitcher_id": 8, "player": "Pitcher Mixed", "game_date": "2026-08-12", "captured_at_utc": "2026-08-12T12:00:00Z", "projection": 4.5, "actual_strikeouts": 6, "history_semantics": HISTORY_SEMANTICS},
    ])
    report = underperformer_report(frame)
    row = report.loc[report["Pitcher"].eq("Pitcher Low")].iloc[0]
    assert row["Below Projection Starts"] == 3
    assert row["Below Projection Rate"] == 1.0
    assert row["Current Below Streak"] == 3
    assert row["2+ K Under Events"] == 2
    assert row["Avg K vs Projection"] < -0.5
    assert row["Underperformer Status"] == "UNDERPERFORMER"

    mixed = report.loc[report["Pitcher"].eq("Pitcher Mixed")].iloc[0]
    assert mixed["Below Projection Starts"] == 1
    assert mixed["Below Projection Rate"] == 1 / 3
    assert mixed["Current Below Streak"] == 0


def test_exact_projection_equal_result_is_neither_crusher_nor_underperformer():
    frame = pd.DataFrame([
        {"pitcher_id": 9, "player": "Pitcher Exact", "game_date": "2026-08-01", "projection": 5.0, "actual_strikeouts": 5, "history_semantics": HISTORY_SEMANTICS},
    ])
    crusher = crusher_report(frame).iloc[0]
    under = underperformer_report(frame).iloc[0]
    assert crusher["Projection Wins"] == 0
    assert under["Below Projection Starts"] == 0


def test_crusher_report_prefers_current_history_semantics():
    frame = pd.DataFrame([
        {"pitcher_id": 1, "player": "Pitcher A", "game_date": "2026-08-01", "projection": 4.0, "actual_strikeouts": 8, "history_semantics": "legacy"},
        {"pitcher_id": 1, "player": "Pitcher A", "game_date": "2026-08-02", "projection": 5.0, "actual_strikeouts": 4, "history_semantics": HISTORY_SEMANTICS},
    ])
    report = crusher_report(frame)
    row = report.iloc[0]
    assert row["Resolved Starts"] == 1
    assert row["Projection Wins"] == 0
    under = underperformer_report(frame).iloc[0]
    assert under["Resolved Starts"] == 1
    assert under["Below Projection Starts"] == 1


def test_transitional_aliases_follow_exact_projection_not_ladder_semantics():
    frame = pd.DataFrame([
        {"pitcher_id": 3, "player": "Pitcher C", "game_date": "2026-08-01", "projection": 5.8, "actual_strikeouts": 5, "history_semantics": HISTORY_SEMANTICS},
    ])
    row = crusher_report(frame).iloc[0]
    assert row["Projection Wins"] == 0
    assert row["Ladder Wins"] == 0
    assert row["Avg K Above Target"] == row["Avg K vs Projection"]
