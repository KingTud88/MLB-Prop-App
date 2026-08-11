from __future__ import annotations

from dataclasses import dataclass


MARKET_STRIKEOUTS = "Strikeouts"
MARKET_OUTS = "Total Outs"
MARKET_HITS = "Hits Allowed"
MARKETS = (MARKET_STRIKEOUTS, MARKET_OUTS, MARKET_HITS)


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
