from __future__ import annotations

from typing import Mapping

import pandas as pd

from engine.bet_lean import aligned_bet_lean
from engine.calibration import calibrate_blend
from engine.hits_calibration import calibrate_hits_blend
from engine.outs_calibration import calibrate_outs_blend
from engine.starter_history import HISTORY_SEMANTICS, MIN_STARTS_FOR_TOP_PLAY

MARKET_STRIKEOUTS = "Strikeouts"
MARKET_OUTS = "Total Outs"
MARKET_HITS = "Hits Allowed"
MARKETS = (MARKET_STRIKEOUTS, MARKET_OUTS, MARKET_HITS)

PROJECTION_COLUMNS = {
    MARKET_STRIKEOUTS: "projection",
    MARKET_OUTS: "outs_projection",
    MARKET_HITS: "hits_projection",
}

LINE_GRIDS = {
    MARKET_STRIKEOUTS: tuple(x + 0.5 for x in range(2, 10)),
    MARKET_OUTS: tuple(x + 0.5 for x in range(13, 19)),
    MARKET_HITS: tuple(x + 0.5 for x in range(3, 9)),
}

# Do not manufacture extreme probabilities by snapping a wildly out-of-domain
# point projection to the nearest supported prop line.
MAX_TARGET_DISTANCE = {
    MARKET_STRIKEOUTS: 1.5,
    MARKET_OUTS: 2.5,
    MARKET_HITS: 1.5,
}


def _num(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def target_line(market: str, projection: float) -> float:
    """Return the nearest modeled half-line for a point projection."""
    grid = LINE_GRIDS[market]
    value = float(projection)
    return float(min(grid, key=lambda line: (abs(float(line) - value), float(line))))


def over_probability(row: Mapping[str, object], market: str, line: float, history: pd.DataFrame) -> float | None:
    """Return the calibrated model probability of going over a modeled half-line."""
    if market == MARKET_STRIKEOUTS:
        cutoff = int(float(line) // 1 + 1)
        if cutoff < 3 or cutoff > 10:
            return None
        sim = _num(row.get(f"sim_{cutoff}p"))
        math_p = _num(row.get(f"math_{cutoff}p"))
        if sim is None or math_p is None:
            return None
        cal = calibrate_blend(history, cutoff)
        return float(cal.weight_simulation * sim + cal.weight_math * math_p)

    key = str(float(line)).replace(".", "_")
    if market == MARKET_HITS:
        sim = _num(row.get(f"hits_sim_over_{key}"))
        math_p = _num(row.get(f"hits_math_over_{key}"))
        if sim is None or math_p is None:
            return None
        cal = calibrate_hits_blend(history, float(line))
        return float(cal.weight_simulation * sim + cal.weight_math * math_p)

    if market == MARKET_OUTS:
        sim = _num(row.get(f"outs_sim_over_{key}"))
        math_p = _num(row.get(f"outs_math_over_{key}"))
        if sim is None or math_p is None:
            return None
        cal = calibrate_outs_blend(history, float(line))
        return float(cal.weight_simulation * sim + cal.weight_math * math_p)

    return None


def build_model_candidate(row: Mapping[str, object], market: str, history: pd.DataFrame) -> dict[str, object] | None:
    """Build one model-first betting candidate without using sportsbook prices."""
    if str(row.get("history_semantics", "")) != HISTORY_SEMANTICS:
        return None
    starter_games = _num(row.get("starter_history_games"))
    if starter_games is None or starter_games < MIN_STARTS_FOR_TOP_PLAY:
        return None

    projection = _num(row.get(PROJECTION_COLUMNS[market]))
    if projection is None:
        return None
    line = target_line(market, projection)
    if abs(float(projection) - float(line)) > MAX_TARGET_DISTANCE[market]:
        return None
    over_p = over_probability(row, market, line, history)
    if over_p is None:
        return None

    decision = aligned_bet_lean(projection, line, over_p, has_market=False)
    if decision.side == "PASS":
        return None

    quality = _num(row.get("data_quality")) or 0.0
    probability = float(decision.model_probability)
    if probability >= 0.65 and quality >= 70:
        status = "STRONG"
    elif probability >= 0.55 and quality >= 60:
        status = "MODEL PLAY"
    else:
        status = "WATCH"

    return {
        "Pitcher": row.get("player", "Unknown"),
        "Market": market,
        "Side": decision.side,
        "Line": line,
        "Projection": projection,
        "Model Probability": probability,
        "Data Quality": int(round(quality)),
        "Starter History": int(starter_games),
        "Status": status,
        "Game PK": row.get("game_pk"),
        "Pitcher ID": row.get("pitcher_id"),
        "Team": row.get("team", ""),
        "Opponent": row.get("opponent", ""),
        "Game Date": row.get("game_date", ""),
        "App Version": row.get("app_version", ""),
        "Probability Semantics": row.get("probability_semantics", ""),
        "History Semantics": row.get("history_semantics", ""),
        "Captured At UTC": row.get("captured_at_utc", ""),
    }


def build_model_board(slate: pd.DataFrame, history: pd.DataFrame, limit: int = 5) -> pd.DataFrame:
    """Rank the slate by the model's own hit probability, never by price or edge."""
    rows: list[dict[str, object]] = []
    for _, snapshot in slate.iterrows():
        row = snapshot.to_dict()
        for market in MARKETS:
            candidate = build_model_candidate(row, market, history)
            if candidate is not None:
                rows.append(candidate)
    if not rows:
        return pd.DataFrame()
    board = pd.DataFrame(rows)
    board = board.sort_values(["Model Probability", "Data Quality"], ascending=[False, False])
    board = board.drop_duplicates(["Pitcher", "Market"], keep="first").head(int(limit)).reset_index(drop=True)
    board.insert(0, "Rank", range(1, len(board) + 1))
    return board
