from __future__ import annotations

import pandas as pd

from training.handedness_matchup_audit import (
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    VERSION,
    build_detail,
    build_gate,
    build_segments,
)


def _context(game_pk: int, pitcher_id: int, hand: str, day: int, *, captured_hour: int = 12) -> dict[str, object]:
    return {
        "game_date": f"2026-08-{day:02d}",
        "game_pk": game_pk,
        "pitcher_id": pitcher_id,
        "player": f"P{pitcher_id}",
        "team": "CLE",
        "opponent": f"O{game_pk % 20:02d}",
        "game_time": f"2026-08-{day:02d}T23:00:00Z",
        "hand_context_captured_at_utc": f"2026-08-{day:02d}T{captured_hour:02d}:00:00Z",
        "pitcher_hand": hand,
        "lineup_source": "CONFIRMED_LINEUP",
        "lineup_confirmed": True,
        "lineup_hash": f"h{game_pk}",
        "lineage": "PRE_GAME_CONFIRMED_MATCH",
        "split_coverage": 1.0,
        "split_available_batters": 9,
        "split_unavailable_batters": 0,
        "same_hand_batters": 4,
        "opposite_hand_batters": 5,
        "opposite_hand_share": 5 / 9,
        "audit_eligible": True,
    }


def _matchup(
    game_pk: int,
    pitcher_id: int,
    day: int,
    *,
    applied: float,
    neutral: float,
    actual: float = 5.0,
) -> dict[str, object]:
    return {
        "game_date": f"2026-08-{day:02d}",
        "game_pk": game_pk,
        "pitcher_id": pitcher_id,
        "player": f"P{pitcher_id}",
        "team": "CLE",
        "opponent": f"O{game_pk % 20:02d}",
        "Applied_Projection": applied,
        "Neutral_Opponent_Projection": neutral,
        "Matchup_Adjustment_K": applied - neutral,
        "Adjustment_Direction": "REDUCE" if applied < neutral else "BOOST",
        "Actual_Strikeouts": actual,
        "Auditable": True,
        "Informative_Adjustment": True,
    }


def _sample(*, lhp_hurts: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    contexts: list[dict[str, object]] = []
    matchups: list[dict[str, object]] = []
    for i in range(60):
        day = 18 + (i % 10)
        game_pk = 1000 + i
        hand = "R" if i < 40 else "L"
        contexts.append(_context(game_pk, 5000 + i, hand, day))
        if hand == "L" and lhp_hurts:
            matchups.append(_matchup(game_pk, 5000 + i, day, applied=5.6, neutral=5.2))
        else:
            matchups.append(_matchup(game_pk, 5000 + i, day, applied=5.2, neutral=5.5))
    return pd.DataFrame(matchups), pd.DataFrame(contexts)


def test_latest_eligible_pregame_context_is_used() -> None:
    matchup = pd.DataFrame([_matchup(1, 2, 18, applied=5.2, neutral=5.5)])
    contexts = pd.DataFrame([
        _context(1, 2, "R", 18, captured_hour=10),
        _context(1, 2, "L", 18, captured_hour=15),
    ])
    detail = build_detail(matchup, contexts)
    assert len(detail) == 1
    assert detail.iloc[0]["pitcher_hand"] == "L"
    assert detail.iloc[0]["Applied_Win"] in (True, 1)


def test_consistent_gate_requires_both_hands_and_diversity() -> None:
    matchup, contexts = _sample(lhp_hurts=False)
    detail = build_detail(matchup, contexts)
    segments = build_segments(detail)
    gate = build_gate(detail, segments).iloc[0]
    assert gate["Finding"] == "CONSISTENT"
    assert gate["RHP_Starts"] == 40
    assert gate["LHP_Starts"] == 20
    assert float(gate["RHP_Relative_MAE_Improvement"]) > 0
    assert float(gate["LHP_Relative_MAE_Improvement"]) > 0
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert VERSION == "handedness-matchup-audit-v1-report-only"


def test_opposite_hand_results_trigger_asymmetry_watch() -> None:
    matchup, contexts = _sample(lhp_hurts=True)
    detail = build_detail(matchup, contexts)
    gate = build_gate(detail, build_segments(detail)).iloc[0]
    assert gate["Finding"] == "ASYMMETRY_WATCH"
    assert float(gate["RHP_Relative_MAE_Improvement"]) > 0
    assert float(gate["LHP_Relative_MAE_Improvement"]) < 0
    assert gate["Recommended_Action"] == "OPEN_HAND_SPECIFIC_REPORT_ONLY_RESEARCH"


def test_empty_evidence_stays_learning() -> None:
    detail = build_detail(pd.DataFrame(), pd.DataFrame())
    segments = build_segments(detail)
    gate = build_gate(detail, segments).iloc[0]
    assert gate["Finding"] == "LEARNING"
    assert gate["Auditable_Starts"] == 0
