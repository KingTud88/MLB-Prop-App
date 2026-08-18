from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd
import pytest

from engine.lineup_context import LINEUP_ACTIVE_ROSTER, LINEUP_CONFIRMED
from training.batter_pitch_whiff_capture import (
    FROZEN_SWING_CODES,
    FROZEN_WHIFF_CODES,
    HISTORICAL_BACKFILL_ALLOWED,
    METRIC_DEFINITION,
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    VERSION,
    build_capture_records,
    extract_batter_pitch_events,
    prior_team_game_pks_from_payload,
    validate_pitch_code_reference,
)


def pitch_code_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for code in sorted(FROZEN_SWING_CODES | {"B", "C"}):
        rows.append({
            "code": code,
            "swingStatus": code in FROZEN_SWING_CODES,
            "swingMissStatus": code in FROZEN_WHIFF_CODES,
            "pitchStatus": True,
        })
    return rows


def pitch_event(code: str, pitch_type: str = "FF") -> dict[str, object]:
    return {
        "isPitch": True,
        "details": {
            "code": code,
            "type": {"code": pitch_type, "description": pitch_type},
        },
    }


def feed_for_batters(batter_ids: tuple[int, ...], events_each: int = 20) -> dict[str, object]:
    plays = []
    for batter_id in batter_ids:
        events = [pitch_event("S" if idx % 4 == 0 else "F", "FF") for idx in range(events_each)]
        plays.append({
            "matchup": {"batter": {"id": batter_id}},
            "playEvents": events,
        })
    return {"liveData": {"plays": {"allPlays": plays}}}


def ten_game_schedule() -> dict[str, object]:
    return {
        "dates": [
            {
                "date": f"2026-08-{day:02d}",
                "games": [{
                    "gamePk": 900000 + day,
                    "gameDate": f"2026-08-{day:02d}T23:00:00Z",
                    "status": {"abstractGameState": "Final"},
                }],
            }
            for day in range(8, 18)
        ]
    }


def projection(lineup_source: str = LINEUP_ACTIVE_ROSTER, lineup_hash: str = "") -> pd.DataFrame:
    return pd.DataFrame([{
        "game_date": "2026-08-18",
        "game_pk": 824803,
        "pitcher_id": 607074,
        "player": "Test Pitcher",
        "team": "NYY",
        "opponent": "BAL",
        "opponent_team_id": 110,
        "game_time": "2026-08-18T22:35:00Z",
        "captured_at_utc": "2026-08-18T04:21:34Z",
        "lineup_source": lineup_source,
        "lineup_confirmed": lineup_source == LINEUP_CONFIRMED,
        "lineup_hash": lineup_hash,
    }])


def test_pitch_code_reference_matches_frozen_mlb_semantics() -> None:
    known, signature = validate_pitch_code_reference(pitch_code_rows())
    assert FROZEN_SWING_CODES <= known
    assert FROZEN_WHIFF_CODES <= known
    assert len(signature) == 64


def test_pitch_code_semantic_drift_fails_closed() -> None:
    rows = pitch_code_rows()
    for row in rows:
        if row["code"] == "S":
            row["swingStatus"] = False
            row["swingMissStatus"] = False
    with pytest.raises(RuntimeError, match="semantics changed"):
        validate_pitch_code_reference(rows)


def test_prior_team_games_are_final_and_strictly_before_target_date() -> None:
    payload = ten_game_schedule()
    payload["dates"].append({
        "date": "2026-08-18",
        "games": [{"gamePk": 999001, "status": {"abstractGameState": "Final"}}],
    })
    payload["dates"].append({
        "date": "2026-08-07",
        "games": [{"gamePk": 999002, "status": {"abstractGameState": "Live"}}],
    })
    game_pks = prior_team_game_pks_from_payload(payload, "2026-08-18", limit=10)
    assert len(game_pks) == 10
    assert 999001 not in game_pks
    assert 999002 not in game_pks
    assert game_pks[0] == 900017


def test_pitch_events_use_whiffs_over_swings_by_batter_and_pitch_type() -> None:
    feed = {
        "liveData": {"plays": {"allPlays": [{
            "matchup": {"batter": {"id": 10}},
            "playEvents": [
                pitch_event("S", "FF"),
                pitch_event("F", "FF"),
                pitch_event("T", "SL"),
                pitch_event("C", "SL"),
                pitch_event("X", "CH"),
                pitch_event("B", "CH"),
            ],
        }]}}
    }
    result = extract_batter_pitch_events([feed], (10,), set(FROZEN_SWING_CODES) | {"B", "C"})
    counts = json.loads(str(result["batter_pitch_counts_json"]))
    assert result["swing_events"] == 4
    assert result["whiff_events"] == 2
    assert counts["10"]["FF"] == {"swings": 2, "whiffs": 1}
    assert counts["10"]["SL"] == {"swings": 1, "whiffs": 1}
    assert counts["10"]["CH"] == {"swings": 1, "whiffs": 0}


def test_live_style_active_roster_capture_is_eligible_with_frozen_prior_games() -> None:
    batter_ids = (101, 102, 103, 104, 105)
    feed = feed_for_batters(batter_ids)
    result = build_capture_records(
        projection(),
        captured_at=pd.Timestamp("2026-08-18T12:00:00Z"),
        pitch_code_resolver=pitch_code_rows,
        roster_resolver=lambda team_id, season: batter_ids,
        schedule_resolver=lambda team_id, before_date: ten_game_schedule(),
        feed_resolver=lambda game_pk: feed,
    )
    row = result.iloc[0]
    assert row["lineage"] == "PRE_GAME_ACTIVE_ROSTER"
    assert row["audit_eligible"] in (True, 1)
    assert row["prior_team_games_with_feed"] == 10
    assert row["swing_events"] == 1000
    assert row["whiff_events"] == 250
    assert row["overall_whiff_rate"] == 0.25
    assert row["batters_with_sample"] == 5
    assert row["metric_definition"] == METRIC_DEFINITION
    rates = json.loads(row["batter_pitch_whiff_rates_json"])
    assert set(rates) == {str(x) for x in batter_ids}
    assert rates["101"]["FF"] == 0.25


def test_confirmed_lineup_hash_mismatch_is_frozen_ineligible() -> None:
    result = build_capture_records(
        projection(LINEUP_CONFIRMED, "saved-hash"),
        captured_at=pd.Timestamp("2026-08-18T12:00:00Z"),
        pitch_code_resolver=pitch_code_rows,
        lineup_resolver=lambda game_pk, team_id: SimpleNamespace(
            confirmed=True,
            fingerprint="different-hash",
            player_ids=(101, 102, 103, 104, 105, 106, 107, 108, 109),
        ),
        roster_resolver=lambda team_id, season: (_ for _ in ()).throw(AssertionError("roster fallback forbidden")),
        schedule_resolver=lambda team_id, before_date: (_ for _ in ()).throw(AssertionError("source fetch forbidden")),
    )
    row = result.iloc[0]
    assert row["audit_eligible"] in (False, 0)
    assert row["lineage"] == "CONFIRMED_LINEUP_HASH_MISMATCH"
    assert row["batters_requested"] == 0


def test_first_frozen_capture_wins_for_same_lineup_state() -> None:
    batter_ids = (101, 102, 103, 104, 105)
    feed = feed_for_batters(batter_ids)
    first = build_capture_records(
        projection(),
        captured_at=pd.Timestamp("2026-08-18T12:00:00Z"),
        pitch_code_resolver=pitch_code_rows,
        roster_resolver=lambda team_id, season: batter_ids,
        schedule_resolver=lambda team_id, before_date: ten_game_schedule(),
        feed_resolver=lambda game_pk: feed,
    )
    second = build_capture_records(
        projection(),
        first,
        captured_at=pd.Timestamp("2026-08-18T13:00:00Z"),
        pitch_code_resolver=pitch_code_rows,
        roster_resolver=lambda team_id, season: (_ for _ in ()).throw(AssertionError("must not recapture")),
        schedule_resolver=lambda team_id, before_date: (_ for _ in ()).throw(AssertionError("must not recapture")),
    )
    assert len(second) == 1
    assert second.iloc[0]["whiff_context_captured_at_utc"] == first.iloc[0]["whiff_context_captured_at_utc"]


def test_contract_is_report_only_and_no_historical_backfill() -> None:
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert HISTORICAL_BACKFILL_ALLOWED is False
    assert VERSION == "batter-pitch-whiff-capture-v1-report-only"
