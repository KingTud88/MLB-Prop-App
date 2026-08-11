import pandas as pd

from engine.model_top_plays import (
    MARKET_HITS,
    MARKET_OUTS,
    MARKET_STRIKEOUTS,
    build_model_board,
    build_model_candidate,
    target_line,
)


def snapshot():
    row = {
        "game_pk": 1,
        "game_date": "2026-08-11",
        "pitcher_id": 99,
        "player": "Test Pitcher",
        "team": "CLE",
        "opponent": "DET",
        "projection": 5.10,
        "hits_projection": 4.40,
        "outs_projection": 17.80,
        "data_quality": 90,
        "probability_semantics": "milestone-ceil-v1",
    }
    for cutoff in range(3, 11):
        row[f"sim_{cutoff}p"] = 0.40 if cutoff == 6 else 0.50
        row[f"math_{cutoff}p"] = 0.40 if cutoff == 6 else 0.50
    for line in (3.5, 4.5, 5.5, 6.5, 7.5, 8.5):
        key = str(line).replace(".", "_")
        value = 0.35 if line == 4.5 else 0.50
        row[f"hits_sim_over_{key}"] = value
        row[f"hits_math_over_{key}"] = value
    for line in (13.5, 14.5, 15.5, 16.5, 17.5, 18.5):
        key = str(line).replace(".", "_")
        value = 0.62 if line == 17.5 else 0.50
        row[f"outs_sim_over_{key}"] = value
        row[f"outs_math_over_{key}"] = value
    return row


def test_target_line_uses_nearest_modeled_half_line():
    assert target_line(MARKET_STRIKEOUTS, 5.10) == 5.5
    assert target_line(MARKET_HITS, 4.40) == 4.5
    assert target_line(MARKET_OUTS, 17.80) == 17.5


def test_candidates_are_projection_aligned_and_price_independent():
    row = snapshot()
    history = pd.DataFrame()
    k = build_model_candidate(row, MARKET_STRIKEOUTS, history)
    hits = build_model_candidate(row, MARKET_HITS, history)
    outs = build_model_candidate(row, MARKET_OUTS, history)

    assert k["Side"] == "UNDER"
    assert round(k["Model Probability"], 3) == 0.600
    assert hits["Side"] == "UNDER"
    assert round(hits["Model Probability"], 3) == 0.650
    assert outs["Side"] == "OVER"
    assert round(outs["Model Probability"], 3) == 0.620
    assert "Odds" not in k
    assert "Edge" not in k


def test_board_ranks_by_model_probability_then_quality():
    row = snapshot()
    board = build_model_board(pd.DataFrame([row]), pd.DataFrame(), limit=5)
    assert list(board["Market"])[:3] == [MARKET_HITS, MARKET_OUTS, MARKET_STRIKEOUTS]
    assert list(board["Model Probability"]) == sorted(board["Model Probability"], reverse=True)
