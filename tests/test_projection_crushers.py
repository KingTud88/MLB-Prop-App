import pandas as pd

from engine.projection_crushers import (
    bettable_k_label,
    bettable_k_result,
    bettable_k_target,
    crusher_report,
    directional_k_result,
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


def test_bettable_k_result_grades_actual_at_target_as_win():
    # Wacha case: 5.07 projects to the playable 5+ milestone, so 5 Ks wins.
    assert bettable_k_result(5.07, 5) == "✅ WIN"
    # Snell case: 4.60 projects to 4+, so both 4 and 10 Ks win.
    assert bettable_k_result(4.60, 10) == "✅ WIN"
    assert bettable_k_result(4.60, 4) == "✅ WIN"
    assert bettable_k_result(4.60, 3) == "❌ MISS"
    assert bettable_k_result(5.99, 5) == "✅ WIN"
    assert bettable_k_result(6.00, 5) == "❌ MISS"
    assert bettable_k_result(2.99, 8) == "NO CALL"
    assert bettable_k_result(5.07, None) == "PENDING"
    # Old callers inherit the new correct milestone semantics.
    assert directional_k_result(5.07, 5) == "✅ WIN"


def test_crusher_report_rewards_repeat_ladder_beats():
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
    assert row["Ladder Wins"] == 3
    assert row["Win Rate"] == 1.0
    assert row["Current Win Streak"] == 3
    assert row["2+ K Crushes"] == 3
    assert row["Crusher Status"] == "🔥 CRUSHER"

    row_b = report.loc[report["Pitcher"].eq("Pitcher B")].iloc[0]
    assert row_b["Ladder Wins"] == 2  # 5 at a 5+ target is correctly a win.


def test_crusher_report_prefers_current_history_semantics():
    frame = pd.DataFrame([
        {"pitcher_id": 1, "player": "Pitcher A", "game_date": "2026-08-01", "projection": 4.0, "actual_strikeouts": 8, "history_semantics": "legacy"},
        {"pitcher_id": 1, "player": "Pitcher A", "game_date": "2026-08-02", "projection": 5.0, "actual_strikeouts": 4, "history_semantics": HISTORY_SEMANTICS},
    ])
    report = crusher_report(frame)
    row = report.iloc[0]
    assert row["Resolved Starts"] == 1
    assert row["Ladder Wins"] == 0
