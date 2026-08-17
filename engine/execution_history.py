from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

import pandas as pd

from engine.bet_lean import aligned_bet_lean
from engine.model_top_plays import MARKET_HITS, MARKET_OUTS, PROJECTION_COLUMNS, over_probability


EXECUTION_HISTORY_VERSION = "frozen-execution-v1"
LEGACY_EXECUTION_BACKFILL_VERSION = "legacy-pregame-execution-backfill-v1"
ACTIONABLE_SIDES = {"OVER", "UNDER"}
FROZEN_SIDES = {"OVER", "UNDER", "PASS"}


@dataclass(frozen=True)
class FrozenExecutionDecision:
    side: str
    model_probability: float | None
    reason: str


def _num(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def _utc(value: object) -> pd.Timestamp | None:
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    return None if pd.isna(parsed) else pd.Timestamp(parsed)


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


def history_resolved_before(history: pd.DataFrame, decision_time: object) -> pd.DataFrame:
    """Return only outcomes that were knowable before a historical execution decision."""
    decision_ts = _utc(decision_time)
    if decision_ts is None or history.empty or "resolved_at_utc" not in history.columns:
        return history.iloc[0:0].copy()
    resolved = pd.to_datetime(history["resolved_at_utc"], errors="coerce", utc=True)
    return history.loc[resolved.notna() & resolved.le(decision_ts)].copy()


def recover_legacy_execution_decision(
    row: Mapping[str, object],
    market: str,
    line: object,
    history: pd.DataFrame,
) -> FrozenExecutionDecision:
    """Recover a missing historical side only when its pregame timing is provable.

    This deliberately ignores final game results. The archived manual-line commit time
    must precede first pitch, the frozen model snapshot must already exist by that
    commit time, and calibration may use only outcomes resolved before that instant.
    """
    threshold = _num(line)
    if threshold is None:
        return FrozenExecutionDecision("UNGRADABLE", None, "legacy_missing_line")

    committed = _utc(row.get("archive_committed_at_utc"))
    game_time = _utc(row.get("game_time"))
    captured = _utc(row.get("captured_at_utc"))
    if committed is None or game_time is None:
        return FrozenExecutionDecision("UNGRADABLE", None, "legacy_missing_timing")
    if committed >= game_time:
        return FrozenExecutionDecision("UNGRADABLE", None, "legacy_line_not_certified_pregame")
    if captured is None or captured > committed:
        return FrozenExecutionDecision("UNGRADABLE", None, "legacy_snapshot_not_certified_before_line")

    prior_history = history_resolved_before(history, committed)
    decision = freeze_execution_decision(row, market, threshold, prior_history)
    # A missing probability path is not a historical PASS; it means the old side
    # cannot be reconstructed faithfully.
    if decision.model_probability is None:
        return FrozenExecutionDecision("UNGRADABLE", None, "legacy_missing_supported_probability_path")
    if decision.side not in FROZEN_SIDES:
        return FrozenExecutionDecision("UNGRADABLE", None, f"legacy_unrecoverable_{decision.reason}")
    return FrozenExecutionDecision(
        decision.side,
        decision.model_probability,
        f"legacy_pregame_backfill|{decision.reason}",
    )


def backfill_legacy_execution_sides(
    archive: pd.DataFrame,
    history: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    """Backfill provable pregame Hits/Outs sides without using postgame outcomes."""
    if archive.empty:
        return archive.copy(), 0
    result = archive.copy()
    specs = (
        (MARKET_OUTS, "manual_outs_line", "manual_outs_side", "manual_outs_decision_probability", "manual_outs_decision_reason", "manual_outs_side_frozen_at_utc"),
        (MARKET_HITS, "manual_hits_allowed_line", "manual_hits_allowed_side", "manual_hits_allowed_decision_probability", "manual_hits_allowed_decision_reason", "manual_hits_allowed_side_frozen_at_utc"),
    )
    for _, _, side_col, prob_col, reason_col, frozen_col in specs:
        if side_col not in result.columns:
            result[side_col] = pd.NA
        if prob_col not in result.columns:
            result[prob_col] = pd.NA
        if reason_col not in result.columns:
            result[reason_col] = ""
        if frozen_col not in result.columns:
            result[frozen_col] = ""

    recovered = 0
    for idx, row in result.iterrows():
        for market, line_col, side_col, prob_col, reason_col, frozen_col in specs:
            line = row.get(line_col)
            if _num(line) is None:
                continue
            side_value = row.get(side_col)
            current_side = "" if side_value is None or pd.isna(side_value) else str(side_value).strip().upper()
            if current_side in FROZEN_SIDES:
                continue
            decision = recover_legacy_execution_decision(row, market, line, history)
            if decision.side not in FROZEN_SIDES:
                continue
            result.at[idx, side_col] = decision.side
            result.at[idx, prob_col] = decision.model_probability
            result.at[idx, reason_col] = decision.reason
            result.at[idx, frozen_col] = str(row.get("archive_committed_at_utc") or "")
            recovered += 1
    return result, recovered


def grade_frozen_execution(side: object, line: object, actual: object) -> str:
    """Grade only a genuinely frozen OVER/UNDER decision against its saved line."""
    threshold = _num(line)
    if threshold is None:
        return "—"
    # Legacy archive rows predate frozen execution sides and therefore carry
    # pandas.NA. Never use boolean coercion (``side or ''``) on pandas.NA:
    # its truth value is intentionally ambiguous. Missing sides remain honest
    # historical UNGRADABLE rows instead of being reconstructed after the fact.
    normalized = "" if side is None or pd.isna(side) else str(side).strip().upper()
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
