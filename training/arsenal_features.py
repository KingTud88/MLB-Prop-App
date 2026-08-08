from __future__ import annotations

from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None and value != "" else default
    except (TypeError, ValueError):
        return default


def build_arsenal_features(arsenal: list[dict[str, Any]] | None) -> dict[str, float]:
    """Aggregate pregame pitcher arsenal data when available.

    Expected pitch rows may contain pitch_type, usage_pct, whiff_pct, putaway_pct,
    velocity, and strikeout_rate. Missing pitch-level data is represented safely.
    """
    rows = arsenal or []
    if not rows:
        return {
            "arsenal_pitch_types": 0.0,
            "arsenal_usage_entropy": 0.0,
            "arsenal_avg_velocity": 0.0,
            "arsenal_whiff_pct": 0.0,
            "arsenal_putaway_pct": 0.0,
            "arsenal_k_rate": 0.0,
        }

    usage = [_f(r.get("usage_pct")) for r in rows]
    total_usage = sum(usage)
    if total_usage > 1.5:
        usage = [x / 100.0 for x in usage]
        total_usage = sum(usage)
    if total_usage <= 0:
        usage = [1.0 / len(rows)] * len(rows)
    else:
        usage = [x / total_usage for x in usage]

    import math
    entropy = -sum(p * math.log(p) for p in usage if p > 0)
    velocity = sum(_f(r.get("velocity")) * p for r, p in zip(rows, usage))
    whiff = sum(_f(r.get("whiff_pct")) * p for r, p in zip(rows, usage))
    putaway = sum(_f(r.get("putaway_pct")) * p for r, p in zip(rows, usage))
    k_rate = sum(_f(r.get("strikeout_rate")) * p for r, p in zip(rows, usage))

    return {
        "arsenal_pitch_types": float(len(rows)),
        "arsenal_usage_entropy": entropy,
        "arsenal_avg_velocity": velocity,
        "arsenal_whiff_pct": whiff,
        "arsenal_putaway_pct": putaway,
        "arsenal_k_rate": k_rate,
    }
