from __future__ import annotations

import pandas as pd

from training.handedness_matchup_audit import build_detail
from training.handedness_matchup_lineage_guard import (
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    VERSION,
    build_effective_context,
    build_gate,
)


def _context(*, captured: str, source: str, eligible: bool, lineage: str, lineup_hash: str = "") -> dict[str, object]:
    return {
        "game_date": "2026-08-18",
        "game_pk": 100,
        "pitcher_id": 200,
        "player": "Pitcher",
        "team": "CLE",
        "opponent": "DET",
        "game_time": "2026-08-18T23:00:00Z",
        "hand_context_captured_at_utc": captured,
        "pitcher_hand": "R",
        "lineup_source": source,
        "lineup_confirmed": source == "CONFIRMED_LINEUP",
        "lineup_hash": lineup_hash,
        "lineage": lineage,
        "split_coverage": 1.0,
        "split_available_batters": 9,
        "split_unavailable_batters": 0,
        "same_hand_batters": 4,
        "opposite_hand_batters": 5,
        "opposite_hand_share": 5 / 9,
        "audit_eligible": eligible,
    }


def _matchup() -> pd.DataFrame:
    return pd.DataFrame([{
        "game_date": "2026-08-18",
        "game_pk": 100,
        "pitcher_id": 200,
        "player": "Pitcher",
        "team": "CLE",
        "opponent": "DET",
        "Applied_Projection": 5.2,
        "Neutral_Opponent_Projection": 5.5,
        "Matchup_Adjustment_K": -0.3,
        "Adjustment_Direction": "REDUCE",
        "Actual_Strikeouts": 5.0,
        "Auditable": True,
        "Informative_Adjustment": True,
    }])


def test_ineligible_confirmed_state_blocks_stale_roster_fallback() -> None:
    raw = pd.DataFrame([
        _context(captured="2026-08-18T10:00:00Z", source="ACTIVE_ROSTER", eligible=True, lineage="PRE_GAME_ACTIVE_ROSTER"),
        _context(captured="2026-08-18T15:00:00Z", source="CONFIRMED_LINEUP", eligible=False, lineage="CONFIRMED_LINEUP_HASH_MISMATCH", lineup_hash="new"),
    ])
    effective = build_effective_context(raw)
    assert len(effective) == 1
    assert effective.iloc[0]["lineage"] == "CONFIRMED_LINEUP_HASH_MISMATCH"
    assert effective.iloc[0]["audit_eligible"] in (False, 0)
    assert build_detail(_matchup(), effective).empty
    gate = build_gate(raw, effective).iloc[0]
    assert gate["Status"] == "STALE_FALLBACK_BLOCKED"
    assert gate["Stale_Fallback_Blocked_Starts"] == 1


def test_valid_confirmed_state_supersedes_roster() -> None:
    raw = pd.DataFrame([
        _context(captured="2026-08-18T10:00:00Z", source="ACTIVE_ROSTER", eligible=True, lineage="PRE_GAME_ACTIVE_ROSTER"),
        _context(captured="2026-08-18T15:00:00Z", source="CONFIRMED_LINEUP", eligible=True, lineage="PRE_GAME_CONFIRMED_MATCH", lineup_hash="h1"),
    ])
    effective = build_effective_context(raw)
    assert len(effective) == 1
    assert effective.iloc[0]["lineup_source"] == "CONFIRMED_LINEUP"
    detail = build_detail(_matchup(), effective)
    assert len(detail) == 1
    gate = build_gate(raw, effective).iloc[0]
    assert gate["Roster_To_Confirmed_Starts"] == 1
    assert gate["Latest_Eligible_Starts"] == 1


def test_postgame_context_is_never_effective() -> None:
    raw = pd.DataFrame([
        _context(captured="2026-08-18T10:00:00Z", source="ACTIVE_ROSTER", eligible=True, lineage="PRE_GAME_ACTIVE_ROSTER"),
        _context(captured="2026-08-18T23:30:00Z", source="CONFIRMED_LINEUP", eligible=True, lineage="PRE_GAME_CONFIRMED_MATCH", lineup_hash="late"),
    ])
    effective = build_effective_context(raw)
    assert len(effective) == 1
    assert effective.iloc[0]["lineup_source"] == "ACTIVE_ROSTER"


def test_contract_is_report_only() -> None:
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert VERSION == "handedness-matchup-lineage-guard-v1-report-only"
