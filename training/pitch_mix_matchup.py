from __future__ import annotations

from typing import Any


def _f(v: Any) -> float:
    try:
        return float(v) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def build_pitch_mix_matchup_features(
    pitcher_hand: str,
    arsenal: list[dict[str, Any]],
    batters: list[dict[str, Any]],
) -> dict[str, float]:
    """Pregame-only pitch-mix x lineup vulnerability aggregates.

    Each arsenal row may contain pitch_type, usage, and batter K/whiff response
    fields. Missing inputs remain neutral rather than being fabricated.
    """
    if not arsenal or not batters:
        return {
            "pitch_mix_matchup_score": 0.0,
            "pitch_mix_same_hand_score": 0.0,
            "pitch_mix_opposite_hand_score": 0.0,
            "pitch_mix_top_pitch_score": 0.0,
        }

    same = [b for b in batters if str(b.get("hand", "")).upper()[:1] == str(pitcher_hand or "").upper()[:1]]
    opp = [b for b in batters if b not in same]

    def score(rows: list[dict[str, Any]]) -> float:
        if not rows:
            return 0.0
        total_usage = sum(max(0.0, _f(p.get("usage"))) for p in arsenal)
        if not total_usage:
            return 0.0
        result = 0.0
        for pitch in arsenal:
            usage = max(0.0, _f(pitch.get("usage"))) / total_usage
            ptype = str(pitch.get("pitch_type", ""))
            vulnerabilities = [
                _f(b.get("pitch_k_rates", {}).get(ptype))
                for b in rows
                if isinstance(b.get("pitch_k_rates"), dict) and ptype
            ]
            if vulnerabilities:
                result += usage * (sum(vulnerabilities) / len(vulnerabilities))
        return result

    all_score = score(batters)
    same_score = score(same)
    opp_score = score(opp)
    top = sorted(arsenal, key=lambda x: _f(x.get("usage")), reverse=True)[:2]
    top_arsenal = score([{**b, "_pitch_mix_focus": True} for b in batters]) if top else 0.0
    return {
        "pitch_mix_matchup_score": all_score,
        "pitch_mix_same_hand_score": same_score,
        "pitch_mix_opposite_hand_score": opp_score,
        "pitch_mix_top_pitch_score": top_arsenal,
    }
