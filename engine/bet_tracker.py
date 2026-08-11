from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping


MARKET_STRIKEOUTS = "Strikeouts"
MARKET_OUTS = "Total Outs"
MARKET_HITS = "Hits Allowed"
MARKETS = (MARKET_STRIKEOUTS, MARKET_OUTS, MARKET_HITS)

PROJECTION_COLUMNS = {
    MARKET_STRIKEOUTS: "projection",
    MARKET_OUTS: "outs_projection",
    MARKET_HITS: "hits_projection",
}

DEFAULT_LINES = {
    MARKET_STRIKEOUTS: 5.5,
    MARKET_OUTS: 15.5,
    MARKET_HITS: 5.5,
}


@dataclass(frozen=True)
class BetGrade:
    result: str
    won: bool | None
    push: bool


def normalize_market(value: object) -> str:
    text = str(value or "").strip().lower().replace("_", " ")
    if not text:
        return MARKET_STRIKEOUTS
    if "hit" in text:
        return MARKET_HITS
    if "strikeout" in text or "strike out" in text:
        return MARKET_STRIKEOUTS
    if "out" in text:
        return MARKET_OUTS
    return MARKET_STRIKEOUTS


def projection_for_market(snapshot: Mapping[str, object] | None, market: object) -> float | None:
    """Return the frozen point projection that matches a Bet Tracker market."""
    if not snapshot:
        return None
    column = PROJECTION_COLUMNS[normalize_market(market)]
    try:
        value = float(snapshot.get(column))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def default_line_for_market(market: object) -> float:
    return DEFAULT_LINES[normalize_market(market)]


def grade_bet(side: object, line: float, actual: float | None, final: bool) -> BetGrade:
    if actual is None:
        return BetGrade("PENDING", None, False)
    side_text = str(side or "").strip().upper()
    line = float(line)
    actual = float(actual)
    if not final:
        if side_text == "OVER":
            return BetGrade("LIVE AHEAD" if actual > line else "LIVE BEHIND", None, False)
        return BetGrade("LIVE AHEAD" if actual < line else "LIVE BEHIND", None, False)
    if actual == line:
        return BetGrade("PUSH", None, True)
    if side_text == "OVER":
        won = actual > line
    else:
        won = actual < line
    return BetGrade("WIN" if won else "LOSS", won, False)


def profit_for(stake: float | None, american_odds: float | None, grade: BetGrade) -> float | None:
    if stake is None or american_odds is None or grade.result not in {"WIN", "LOSS", "PUSH"}:
        return None
    stake = float(stake)
    odds = float(american_odds)
    if stake < 0:
        return None
    if grade.result == "PUSH":
        return 0.0
    if grade.result == "LOSS":
        return -stake
    if odds > 0:
        return stake * odds / 100.0
    if odds < 0:
        return stake * 100.0 / abs(odds)
    return None
