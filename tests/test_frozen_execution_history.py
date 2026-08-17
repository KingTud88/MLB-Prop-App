from datetime import datetime, timezone

import pandas as pd

from engine.execution_history import (
    EXECUTION_HISTORY_VERSION,
    LEGACY_EXECUTION_BACKFILL_VERSION,
    backfill_legacy_execution_sides,
    freeze_execution_decision,
    grade_frozen_execution,
    history_resolved_before,
    is_pregame_execution_window,
    recover_legacy_execution_decision,
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
    assert grade_frozen_execution(pd.NA, 5.5, 2) == "⚪ UNGRADABLE"
    assert grade_frozen_execution(None, 5.5, 2) == "⚪ UNGRADABLE"
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


def test_history_backfill_only_uses_results_known_before_manual_line_time():
    history = pd.DataFrame(
        [
            {
                "history_semantics": "starter-only-v1",
                "resolved_at_utc": "2026-08-16T16:00:00Z",
                "actual_outs": 18,
                "outs_sim_over_15_5": 0.8,
                "outs_math_over_15_5": 0.8,
            },
            {
                "history_semantics": "starter-only-v1",
                "resolved_at_utc": "2026-08-16T18:00:00Z",
                "actual_outs": 10,
                "outs_sim_over_15_5": 0.1,
                "outs_math_over_15_5": 0.1,
            },
        ]
    )
    prior = history_resolved_before(history, "2026-08-16T16:57:25Z")
    assert len(prior) == 1
    assert float(prior.iloc[0]["actual_outs"]) == 18


def test_legacy_pregame_line_can_recover_side_without_using_final_result():
    row = {
        "game_time": "2026-08-16T18:10:00Z",
        "captured_at_utc": "2026-08-16T14:50:37Z",
        "archive_committed_at_utc": "2026-08-16T16:57:25Z",
        "outs_projection": 13.90,
        "outs_sim_over_15_5": 0.30,
        "outs_math_over_15_5": 0.30,
        "actual_outs": 99,
    }
    decision = recover_legacy_execution_decision(row, MARKET_OUTS, 15.5, pd.DataFrame())
    assert decision.side == "UNDER"
    assert abs(float(decision.model_probability) - 0.70) < 1e-9
    assert decision.reason.startswith("legacy_pregame_backfill|")

    changed_actual = dict(row, actual_outs=0)
    second = recover_legacy_execution_decision(changed_actual, MARKET_OUTS, 15.5, pd.DataFrame())
    assert second == decision


def test_legacy_backfill_rejects_post_start_or_ambiguous_timing():
    base = {
        "captured_at_utc": "2026-08-16T14:50:37Z",
        "outs_projection": 13.90,
        "outs_sim_over_15_5": 0.30,
        "outs_math_over_15_5": 0.30,
    }
    post_start = dict(base, game_time="2026-08-16T18:10:00Z", archive_committed_at_utc="2026-08-16T18:15:00Z")
    assert recover_legacy_execution_decision(post_start, MARKET_OUTS, 15.5, pd.DataFrame()).side == "UNGRADABLE"

    missing_time = dict(base, game_time="2026-08-16T18:10:00Z", archive_committed_at_utc="")
    assert recover_legacy_execution_decision(missing_time, MARKET_OUTS, 15.5, pd.DataFrame()).side == "UNGRADABLE"


def test_archive_backfill_writes_side_probability_reason_and_original_commit_time():
    archive = pd.DataFrame(
        [
            {
                "game_time": "2026-08-16T18:10:00Z",
                "captured_at_utc": "2026-08-16T14:50:37Z",
                "archive_committed_at_utc": "2026-08-16T16:57:25Z",
                "outs_projection": 13.90,
                "outs_sim_over_15_5": 0.30,
                "outs_math_over_15_5": 0.30,
                "manual_outs_line": 15.5,
            }
        ]
    )
    result, recovered = backfill_legacy_execution_sides(archive, pd.DataFrame())
    assert recovered == 1
    assert result.loc[0, "manual_outs_side"] == "UNDER"
    assert abs(float(result.loc[0, "manual_outs_decision_probability"]) - 0.70) < 1e-9
    assert str(result.loc[0, "manual_outs_decision_reason"]).startswith("legacy_pregame_backfill|")
    assert result.loc[0, "manual_outs_side_frozen_at_utc"] == "2026-08-16T16:57:25Z"


def test_execution_history_integration_contracts():
    assert EXECUTION_HISTORY_VERSION == "frozen-execution-v1"
    assert LEGACY_EXECUTION_BACKFILL_VERSION == "legacy-pregame-execution-backfill-v1"
    daily = open("pages/5_Daily_Projection_Run.py", encoding="utf-8").read()
    history = open("pages/4_Projection_History.py", encoding="utf-8").read()
    storage = open("training/projection_storage.py", encoding="utf-8").read()
    assert "manual_outs_side" in daily and "manual_hits_allowed_side" in daily
    assert "side_not_frozen_pregame" in daily
    assert "grade_frozen_execution" in history
    assert "backfill_legacy_execution_sides" in history
    assert '"Outs Side"' in history and '"Outs Bet Result"' in history
    assert '"Hits Side"' in history and '"Hits Bet Result"' in history
    assert '"manual_outs_line", "manual_outs_side", "actual_outs", "outs_bet_result"' in history
    assert '"manual_hits_allowed_line", "manual_hits_allowed_side", "actual_hits_allowed", "hits_bet_result"' in history
    archive_block = history[history.index("archive_columns = ["):history.index("unique_dates =", history.index("archive_columns = ["))]
    assert '"manual_outs_side"' in archive_block and '"archive_outs_bet_result"' in archive_block
    assert '"manual_hits_allowed_side"' in archive_block and '"archive_hits_bet_result"' in archive_block
    assert "manual_outs_side_frozen_at_utc" in storage
    assert "manual_hits_allowed_side_frozen_at_utc" in storage
