from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

import pandas as pd

from engine.bet_lean import aligned_bet_lean
from engine.model_top_plays import MARKET_HITS, MARKET_OUTS, PROJECTION_COLUMNS, over_probability


EXECUTION_HISTORY_VERSION = "frozen-execution-v1"
ACTIONABLE_SIDES = {"OVER", "UNDER"}


@dataclass(frozen=True)
class FrozenExecutionDecision:
    side: str
    model_probability: float | None
    reason: str


def _num(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def is_pregame_execution_window(row: Mapping[str, object], *, now_utc: datetime | None = None) -> bool:
    """Return True only when the row can still be certified as pregame."""
    game_time = pd.to_datetime(row.get("game_time"), errors="coerce", utc=True)
    if pd.isna(game_time):
        return False
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return pd.Timestamp(now).tz_convert("UTC") < game_time


def freeze_execution_decision(
    row: Mapping[str, object],
    market: str,
    line: object,
    history: pd.DataFrame,
) -> FrozenExecutionDecision:
    """Freeze the existing model lean for a real Hits/Outs sportsbook line."""
    if market not in {MARKET_HITS, MARKET_OUTS}:
        return FrozenExecutionDecision("UNGRADABLE", None, "unsupported_market")
    threshold = _num(line)
    projection = _num(row.get(PROJECTION_COLUMNS[market]))
    if threshold is None or projection is None:
        return FrozenExecutionDecision("UNGRADABLE", None, "missing_line_or_projection")
    over_p = over_probability(row, market, threshold, history)
    if over_p is None:
        return FrozenExecutionDecision("PASS", None, "missing_supported_probability_path")
    decision = aligned_bet_lean(projection, threshold, over_p, has_market=False)
    return FrozenExecutionDecision(decision.side, float(decision.model_probability), decision.reason)


def grade_frozen_execution(side: object, line: object, actual: object) -> str:
    """Grade only a genuinely frozen OVER/UNDER decision against its saved line."""
    threshold = _num(line)
    if threshold is None:
        return "—"
    normalized = str(side or "").strip().upper()
    if normalized in {"PASS", "NO BET"}:
        return "NO BET"
    if normalized not in ACTIONABLE_SIDES:
        return "⚪ UNGRADABLE"
    result = _num(actual)
    if result is None:
        return "PENDING"
    if abs(result - threshold) <= 1e-9:
        return "➖ PUSH"
    won = result > threshold if normalized == "OVER" else result < threshold
    return "✅ WIN" if won else "❌ LOSS"
