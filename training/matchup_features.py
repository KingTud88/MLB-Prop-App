from __future__ import annotations

from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None and value != "" else default
    except (TypeError, ValueError):
        return default


def build_matchup_features(pitcher_hand: str, batters: list[dict[str, Any]]) -> dict[str, float]:
    """Aggregate batter-vs-pitcher-hand matchup features using pregame inputs only."""
    hand = str(pitcher_hand or "").upper()[:1]
    same = [b for b in batters if str(b.get("hand", "")).upper()[:1] == hand]
    opposite = [b for b in batters if b not in same]

    def avg(rows: list[dict[str, Any]], key: str) -> float:
        return sum(_f(r.get(key)) for r in rows) / len(rows) if rows else 0.0

    return {
        "lineup_size": float(len(batters)),
        "same_hand_batters": float(len(same)),
        "opposite_hand_batters": float(len(opposite)),
        "lineup_k_rate": avg(batters, "strikeout_rate"),
        "same_hand_k_rate": avg(same, "strikeout_rate_same_hand"),
        "opposite_hand_k_rate": avg(opposite, "strikeout_rate_opposite_hand"),
        "lineup_k_rate_weighted": avg(batters, "projected_k_probability"),
        "top3_k_rate": avg(sorted(batters, key=lambda x: _f(x.get("strikeout_rate")), reverse=True)[:3], "strikeout_rate"),
    }
