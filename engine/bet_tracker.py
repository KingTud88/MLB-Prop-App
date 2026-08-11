from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from typing import Mapping, Sequence


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


def make_bet_record(
    *,
    player: str,
    market: object,
    game_date: str,
    line: float,
    side: str,
    american_odds: int | float,
    stake: float = 1.0,
    book: str = "",
    projection: float | None = None,
    model_probability: float | None = None,
    implied_probability: float | None = None,
    edge: float | None = None,
    confidence: object = "",
    game_pk: int | None = None,
    pitcher_id: int | None = None,
    entered_at_utc: str | None = None,
    source: str = "",
    data_quality: float | None = None,
    app_version: str = "",
    probability_semantics: str = "",
    snapshot_captured_at_utc: str = "",
) -> dict[str, object]:
    """Build the canonical persistent Bet Tracker record used by every app surface."""
    side_text = str(side or "").strip().title()
    if side_text not in {"Over", "Under"}:
        raise ValueError("side must be Over or Under")
    return {
        "bet_type": "Straight",
        "parlay_legs": "",
        "player": str(player).strip(),
        "market": normalize_market(market),
        "game_date": str(game_date)[:10],
        "line": float(line),
        "side": side_text,
        "american_odds": int(round(float(american_odds))),
        "stake": float(stake),
        "book": str(book or "").strip(),
        "entered_at_utc": entered_at_utc or datetime.now(timezone.utc).isoformat(),
        "projection": "" if projection is None else float(projection),
        "model_probability": "" if model_probability is None else float(model_probability),
        "implied_probability": "" if implied_probability is None else float(implied_probability),
        "edge": "" if edge is None else float(edge),
        "confidence": "" if confidence is None else confidence,
        "actual_strikeouts": "",
        "game_pk": "" if game_pk is None else int(game_pk),
        "pitcher_id": "" if pitcher_id is None else int(pitcher_id),
        "source": str(source or "").strip(),
        "data_quality": "" if data_quality is None else float(data_quality),
        "app_version": str(app_version or ""),
        "probability_semantics": str(probability_semantics or ""),
        "snapshot_captured_at_utc": str(snapshot_captured_at_utc or ""),
    }


def american_to_decimal(american_odds: int | float) -> float:
    odds = float(american_odds)
    if odds > 0:
        return 1.0 + odds / 100.0
    if odds < 0:
        return 1.0 + 100.0 / abs(odds)
    raise ValueError("American odds cannot be zero")


def decimal_to_american(decimal_odds: float) -> int:
    dec = float(decimal_odds)
    if dec <= 1.0:
        raise ValueError("Decimal odds must be greater than 1")
    if dec >= 2.0:
        return int(round((dec - 1.0) * 100.0))
    return int(round(-100.0 / (dec - 1.0)))


def combined_parlay_odds(american_odds: Sequence[int | float]) -> int:
    """Estimated standard parlay price from independent listed leg prices."""
    prices = list(american_odds)
    if len(prices) < 2:
        raise ValueError("A parlay needs at least two legs")
    decimal = 1.0
    for price in prices:
        decimal *= american_to_decimal(price)
    return decimal_to_american(decimal)


def make_parlay_record(
    *,
    legs: Sequence[Mapping[str, object]],
    stake: float,
    game_date: str,
    book: str = "",
    american_odds: int | float | None = None,
    entered_at_utc: str | None = None,
    source: str = "",
) -> dict[str, object]:
    """Build one tracker row representing an entire parlay ticket."""
    cleaned: list[dict[str, object]] = []
    for leg in legs:
        side = str(leg.get("side", "")).strip().title()
        if side not in {"Over", "Under"}:
            raise ValueError("Every parlay leg needs an Over or Under side")
        cleaned.append({
            "player": str(leg.get("player", "")).strip(),
            "market": normalize_market(leg.get("market")),
            "game_date": str(leg.get("game_date", game_date))[:10],
            "line": float(leg.get("line")),
            "side": side,
            "american_odds": "" if leg.get("american_odds") in {None, ""} else int(round(float(leg.get("american_odds")))) ,
            "game_pk": "" if leg.get("game_pk") in {None, ""} else int(float(leg.get("game_pk"))),
            "pitcher_id": "" if leg.get("pitcher_id") in {None, ""} else int(float(leg.get("pitcher_id"))),
            "projection": leg.get("projection", ""),
            "model_probability": leg.get("model_probability", ""),
            "data_quality": leg.get("data_quality", ""),
            "app_version": leg.get("app_version", ""),
            "probability_semantics": leg.get("probability_semantics", ""),
            "snapshot_captured_at_utc": leg.get("snapshot_captured_at_utc", ""),
        })
    if len(cleaned) < 2:
        raise ValueError("A parlay needs at least two legs")
    return {
        "bet_type": "Parlay",
        "parlay_legs": json.dumps(cleaned, separators=(",", ":")),
        "player": f"{len(cleaned)}-leg parlay",
        "market": "Parlay",
        "game_date": str(game_date)[:10],
        "line": "",
        "side": "",
        "american_odds": "" if american_odds is None else int(round(float(american_odds))),
        "stake": float(stake),
        "book": str(book or "").strip(),
        "entered_at_utc": entered_at_utc or datetime.now(timezone.utc).isoformat(),
        "projection": "",
        "model_probability": "",
        "implied_probability": "",
        "edge": "",
        "confidence": "",
        "actual_strikeouts": "",
        "game_pk": "",
        "pitcher_id": "",
        "source": str(source or "").strip(),
        "data_quality": "",
        "app_version": "",
        "probability_semantics": "",
        "snapshot_captured_at_utc": "",
    }


def parse_parlay_legs(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    try:
        data = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def grade_parlay(leg_grades: Sequence[BetGrade]) -> BetGrade:
    grades = list(leg_grades)
    if not grades:
        return BetGrade("PENDING", None, False)
    if any(g.result == "LOSS" for g in grades):
        return BetGrade("LOSS", False, False)
    if any(g.result == "LIVE BEHIND" for g in grades):
        return BetGrade("LIVE BEHIND", None, False)
    if any(g.result in {"PENDING", "LIVE AHEAD"} for g in grades):
        return BetGrade("LIVE AHEAD" if all(g.result in {"WIN", "PUSH", "LIVE AHEAD"} for g in grades) else "PENDING", None, False)
    if all(g.result == "PUSH" for g in grades):
        return BetGrade("PUSH", None, True)
    if any(g.result == "PUSH" for g in grades):
        # A pushed leg usually reprices the remaining ticket; do not invent P/L.
        return BetGrade("PUSH LEG", None, True)
    if all(g.result == "WIN" for g in grades):
        return BetGrade("WIN", True, False)
    return BetGrade("PENDING", None, False)


def result_cell_css(value: object) -> str:
    """Readable status colors for the tracker result column."""
    text = str(value or "").strip().upper()
    if text == "WIN":
        return "color:#49efb0;font-weight:900"
    if text == "LOSS":
        return "color:#ff4b4b;font-weight:900"
    if text in {"PUSH", "PUSH LEG"}:
        return "color:#ffd166;font-weight:900"
    if text == "LIVE AHEAD":
        return "color:#49efb0;font-weight:800"
    if text == "LIVE BEHIND":
        return "color:#ff9f43;font-weight:800"
    return "color:#8fa5b7;font-weight:800"


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
