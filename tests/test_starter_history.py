import pandas as pd

from engine.starter_history import (
    HISTORY_SEMANTICS,
    combine_starter_history,
    has_minimum_starts,
    starter_only,
)


def _frame(rows):
    return pd.DataFrame(rows)


def test_starter_only_excludes_relief_appearances():
    frame = _frame([
        {"date": "2026-04-01", "opponent": "A", "games_started": 1, "outs": 18, "k": 6},
        {"date": "2026-04-05", "opponent": "B", "games_started": 0, "outs": 3, "k": 1},
        {"date": "2026-04-10", "opponent": "C", "games_started": 1, "outs": 17, "k": 5},
    ])
    starts = starter_only(frame)
    assert list(starts["outs"]) == [18, 17]
    assert (starts["games_started"] == 1).all()


def test_missing_start_flag_is_not_guessed():
    frame = _frame([{"date": "2026-04-01", "outs": 18, "k": 6}])
    assert starter_only(frame).empty


def test_current_and_prior_starts_combine_in_chronological_order():
    prior = _frame([
        {"date": "2025-09-20", "opponent": "A", "games_started": 1, "outs": 18},
        {"date": "2025-09-25", "opponent": "B", "games_started": 0, "outs": 2},
    ])
    current = _frame([
        {"date": "2026-04-05", "opponent": "C", "games_started": 1, "outs": 16},
        {"date": "2026-04-11", "opponent": "D", "games_started": 1, "outs": 19},
    ])
    combined = combine_starter_history(current, prior)
    assert list(combined["outs"]) == [18, 16, 19]
    assert has_minimum_starts(combined, 3)


def test_history_semantics_marks_new_input_contract():
    assert HISTORY_SEMANTICS == "starter-only-v1"
