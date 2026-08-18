from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from engine.lineup_context import LINEUP_ACTIVE_ROSTER, LINEUP_CONFIRMED
from training.handedness_matchup_capture import (
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    VERSION,
    build_capture_records,
)


def _projection(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "game_date": "2026-08-18",
        "game_pk": 123,
        "pitcher_id": 456,
        "player": "Starter",
        "team": "CLE",
        "opponent": "BOS",
        "opponent_team_id": 111,
        "game_time": "2026-08-18T23:00:00Z",
        "captured_at_utc": "2026-08-18T15:00:00Z",
        "lineup_source": LINEUP_CONFIRMED,
        "lineup_confirmed": True,
        "lineup_hash": "abc123",
        "lineup_batters": 9,
        "matchup_pa": 1800,
        "opponent_k_pct": 24.1,
    }
    row.update(overrides)
    return row


def _batters(*args: object, **kwargs: object) -> pd.DataFrame:
    return pd.DataFrame({
        "Hand": ["L", "L", "R", "R", "R", "S", "S", "R", "L"],
        "Split Available": [True, True, True, True, True, True, False, True, True],
    })


def test_confirmed_hash_match_captures_lineage_and_hand_mix() -> None:
    context = SimpleNamespace(
        confirmed=True,
        fingerprint="abc123",
        player_ids=tuple(range(1, 10)),
        spots=tuple((pid, pid) for pid in range(1, 10)),
    )
    out = build_capture_records(
        pd.DataFrame([_projection()]),
        captured_at=pd.Timestamp("2026-08-18T16:00:00Z"),
        hand_resolver=lambda _: "R",
        lineup_resolver=lambda *_: context,
        batters_resolver=_batters,
    )
    row = out.iloc[0]
    assert row["lineage"] == "PRE_GAME_CONFIRMED_MATCH"
    assert row["audit_eligible"] in (True, 1)
    assert row["pitcher_hand"] == "R"
    assert row["batter_left"] == 3
    assert row["batter_right"] == 4
    assert row["batter_switch"] == 2
    assert row["opposite_hand_batters"] == 5
    assert abs(float(row["opposite_hand_share"]) - 5 / 9) < 1e-12
    assert row["split_available_batters"] == 8
    assert abs(float(row["split_coverage"]) - 8 / 9) < 1e-12
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert VERSION == "handedness-matchup-context-v1"


def test_confirmed_hash_mismatch_is_not_auditable() -> None:
    context = SimpleNamespace(
        confirmed=True,
        fingerprint="different",
        player_ids=tuple(range(1, 10)),
        spots=tuple((pid, pid) for pid in range(1, 10)),
    )
    out = build_capture_records(
        pd.DataFrame([_projection()]),
        captured_at=pd.Timestamp("2026-08-18T16:00:00Z"),
        hand_resolver=lambda _: "L",
        lineup_resolver=lambda *_: context,
        batters_resolver=_batters,
    )
    row = out.iloc[0]
    assert row["lineage"] == "CONFIRMED_LINEUP_HASH_MISMATCH"
    assert row["audit_eligible"] in (False, 0)
    assert row["lineup_batters"] == 0


def test_active_roster_context_dedupes_and_postgame_is_ignored() -> None:
    projection = _projection(
        lineup_source=LINEUP_ACTIVE_ROSTER,
        lineup_confirmed=False,
        lineup_hash="",
    )
    first = build_capture_records(
        pd.DataFrame([projection]),
        captured_at=pd.Timestamp("2026-08-18T16:00:00Z"),
        hand_resolver=lambda _: "L",
        batters_resolver=_batters,
    )
    second = build_capture_records(
        pd.DataFrame([projection]),
        first,
        captured_at=pd.Timestamp("2026-08-18T17:00:00Z"),
        hand_resolver=lambda _: "L",
        batters_resolver=_batters,
    )
    assert len(second) == 1
    assert second.iloc[0]["lineage"] == "PRE_GAME_ACTIVE_ROSTER"
    postgame = build_capture_records(
        pd.DataFrame([_projection(game_pk=999)]),
        second,
        captured_at=pd.Timestamp("2026-08-19T00:00:00Z"),
        hand_resolver=lambda _: "R",
        batters_resolver=_batters,
    )
    assert len(postgame) == 1
