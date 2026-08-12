import pandas as pd

from engine.model_health import (
    health_from_walk_forward,
    market_health_map,
    walk_forward_top5,
)
from engine.model_top_plays import MARKET_STRIKEOUTS, build_model_candidate
from engine.starter_history import HISTORY_SEMANTICS


def k_snapshot(day: str, game_pk: int, pitcher_id: int, actual: int) -> dict:
    row = {
        "game_pk": game_pk,
        "game_date": day,
        "pitcher_id": pitcher_id,
        "player": f"Pitcher {pitcher_id}",
        "team": "CLE",
        "opponent": "DET",
        "projection": 5.10,
        "data_quality": 90,
        "probability_semantics": "milestone-ceil-v1",
        "history_semantics": HISTORY_SEMANTICS,
        "starter_history_games": 12,
        "captured_at_utc": f"{day}T12:00:00Z",
        "actual_strikeouts": actual,
    }
    for cutoff in range(3, 11):
        value = 0.40 if cutoff == 6 else 0.50
        row[f"sim_{cutoff}p"] = value
        row[f"math_{cutoff}p"] = value
    return row


def test_walk_forward_uses_only_prior_dates_not_same_day_results():
    history = pd.DataFrame([
        k_snapshot("2026-08-01", 1, 101, 4),
        k_snapshot("2026-08-02", 2, 102, 4),
        k_snapshot("2026-08-02", 3, 103, 8),
    ])
    replay = walk_forward_top5(history)
    first = replay.loc[replay["Walk Forward Date"].eq("2026-08-01")]
    second = replay.loc[replay["Walk Forward Date"].eq("2026-08-02")]
    assert set(first["Training Rows"]) == {0}
    assert set(second["Training Rows"]) == {1}
    assert len(second) == 2


def test_walk_forward_grades_frozen_model_side_after_selection():
    history = pd.DataFrame([
        k_snapshot("2026-08-01", 1, 101, 4),
        k_snapshot("2026-08-02", 2, 102, 8),
    ])
    replay = walk_forward_top5(history)
    assert list(replay["Side"]) == ["UNDER", "UNDER"]
    assert list(replay["Hit"]) == [True, False]
    assert list(replay["Actual"]) == [4.0, 8.0]


def test_health_learns_first_then_blocks_only_after_enough_bad_evidence():
    learning = pd.DataFrame({
        "Market": [MARKET_STRIKEOUTS] * 10,
        "Model Probability": [0.80] * 10,
        "Hit": [False] * 10,
    })
    report = health_from_walk_forward(learning, min_observations=30)
    row = report.loc[report["Market"].eq(MARKET_STRIKEOUTS)].iloc[0]
    assert row["Status"] == "LEARNING"
    assert bool(row["Eligible"]) is True

    bad = pd.DataFrame({
        "Market": [MARKET_STRIKEOUTS] * 35,
        "Model Probability": [0.80] * 35,
        "Hit": [False] * 35,
    })
    report = health_from_walk_forward(bad, min_observations=30)
    row = report.loc[report["Market"].eq(MARKET_STRIKEOUTS)].iloc[0]
    assert row["Status"] == "BLOCKED"
    assert bool(row["Eligible"]) is False
    assert market_health_map(report)[MARKET_STRIKEOUTS] == "BLOCKED"


def test_blocked_market_cannot_build_top_play_candidate():
    row = k_snapshot("2026-08-03", 4, 104, 4)
    candidate = build_model_candidate(
        row,
        MARKET_STRIKEOUTS,
        pd.DataFrame(),
        market_health={MARKET_STRIKEOUTS: "BLOCKED"},
    )
    assert candidate is None
