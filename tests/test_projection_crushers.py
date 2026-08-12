import pandas as pd

from engine.projection_crushers import crusher_report, directional_k_result
from engine.starter_history import HISTORY_SEMANTICS


def test_directional_k_result_grades_actual_above_projection_as_win():
    assert directional_k_result(4.60, 10) == "✅ WIN"
    assert directional_k_result(4.60, 5) == "✅ WIN"
    assert directional_k_result(4.60, 4) == "❌ MISS"
    assert directional_k_result(None, 4) == "PENDING"


def test_crusher_report_rewards_repeat_projection_beats():
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
    assert row["Crusher Status"] == "🔥 CRUSHER"


def test_crusher_report_prefers_current_history_semantics():
    frame = pd.DataFrame([
        {"pitcher_id": 1, "player": "Pitcher A", "game_date": "2026-08-01", "projection": 4.0, "actual_strikeouts": 8, "history_semantics": "legacy"},
        {"pitcher_id": 1, "player": "Pitcher A", "game_date": "2026-08-02", "projection": 5.0, "actual_strikeouts": 4, "history_semantics": HISTORY_SEMANTICS},
    ])
    report = crusher_report(frame)
    row = report.iloc[0]
    assert row["Resolved Starts"] == 1
    assert row["Projection Wins"] == 0
