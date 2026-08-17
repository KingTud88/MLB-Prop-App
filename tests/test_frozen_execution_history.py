from datetime import datetime, timezone

import pandas as pd

from engine.execution_history import (
    EXECUTION_HISTORY_VERSION,
    freeze_execution_decision,
    grade_frozen_execution,
    is_pregame_execution_window,
)
from engine.model_top_plays import MARKET_HITS, MARKET_OUTS


def test_true_execution_grading_requires_frozen_side_and_line():
    assert grade_frozen_execution("OVER", 5.5, 6) == "✅ WIN"
    assert grade_frozen_execution("OVER", 5.5, 5) == "❌ LOSS"
    assert grade_frozen_execution("UNDER", 17.5, 17) == "✅ WIN"
    assert grade_frozen_execution("UNDER", 17.5, 18) == "❌ LOSS"
    assert grade_frozen_execution("OVER", 17.0, 17) == "➖ PUSH"
    assert grade_frozen_execution("PASS", 5.5, 2) == "NO BET"
    assert grade_frozen_execution("", 5.5, 2) == "⚪ UNGRADABLE"
    assert grade_frozen_execution("UNDER", 5.5, None) == "PENDING"
    assert grade_frozen_execution("UNDER", None, 4) == "—"


def test_pregame_window_requires_known_future_first_pitch():
    now = datetime(2026, 8, 16, 20, 0, tzinfo=timezone.utc)
    assert is_pregame_execution_window({"game_time": "2026-08-16T23:00:00Z"}, now_utc=now)
    assert not is_pregame_execution_window({"game_time": "2026-08-16T19:00:00Z"}, now_utc=now)
    assert not is_pregame_execution_window({}, now_utc=now)


def test_hits_and_outs_freeze_existing_aligned_bet_lean():
    history = pd.DataFrame()
    hits_row = {"hits_projection": 4.7, "hits_sim_over_5_5": 0.30, "hits_math_over_5_5": 0.30}
    hits = freeze_execution_decision(hits_row, MARKET_HITS, 5.5, history)
    assert hits.side == "UNDER"
    assert abs(float(hits.model_probability) - 0.70) < 1e-9

    outs_row = {"outs_projection": 17.2, "outs_sim_over_15_5": 0.70, "outs_math_over_15_5": 0.70}
    outs = freeze_execution_decision(outs_row, MARKET_OUTS, 15.5, history)
    assert outs.side == "OVER"
    assert abs(float(outs.model_probability) - 0.70) < 1e-9


def test_execution_history_integration_contracts():
    assert EXECUTION_HISTORY_VERSION == "frozen-execution-v1"
    daily = open("pages/5_Daily_Projection_Run.py", encoding="utf-8").read()
    history = open("pages/4_Projection_History.py", encoding="utf-8").read()
    storage = open("training/projection_storage.py", encoding="utf-8").read()
    assert "manual_outs_side" in daily and "manual_hits_allowed_side" in daily
    assert "side_not_frozen_pregame" in daily
    assert "grade_frozen_execution" in history
    assert '"Outs Side"' in history and '"Outs Bet Result"' in history
    assert '"Hits Side"' in history and '"Hits Bet Result"' in history
    assert "manual_outs_side_frozen_at_utc" in storage
    assert "manual_hits_allowed_side_frozen_at_utc" in storage
