from __future__ import annotations

import json

import pandas as pd

from training.pitch_arsenal_capture import (
    PRODUCTION_AUTHORITY,
    REPORT_ONLY,
    VERSION,
    build_capture_records,
    extract_pitch_summary,
    prior_game_pks_from_payload,
)


def _game_log() -> dict[str, object]:
    return {
        "stats": [{
            "splits": [
                {"date": "2026-08-18", "game": {"gamePk": 118}},
                {"date": "2026-08-10", "game": {"gamePk": 110}},
                {"date": "2026-08-03", "game": {"gamePk": 103}},
                {"date": "2026-07-28", "game": {"gamePk": 98}},
            ]
        }]
    }


def _feed(pitcher_id: int, *, ff: int = 24, sl: int = 12, unknown: int = 0) -> dict[str, object]:
    events: list[dict[str, object]] = []
    for _ in range(ff):
        events.append({
            "isPitch": True,
            "details": {"type": {"code": "FF", "description": "Four-Seam Fastball"}},
        })
    for _ in range(sl):
        events.append({
            "isPitch": True,
            "details": {"type": {"code": "SL", "description": "Slider"}},
        })
    for _ in range(unknown):
        events.append({"isPitch": True, "details": {}})
    return {
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "matchup": {"pitcher": {"id": pitcher_id}},
                        "playEvents": events,
                    },
                    {
                        "matchup": {"pitcher": {"id": pitcher_id + 1}},
                        "playEvents": [
                            {"isPitch": True, "details": {"type": {"code": "CH"}}}
                        ],
                    },
                ]
            }
        }
    }


def _projection(*, game_time: str = "2026-08-18T23:00:00Z") -> pd.DataFrame:
    return pd.DataFrame([{
        "game_date": "2026-08-18",
        "game_pk": 500,
        "pitcher_id": 55,
        "player": "Starter",
        "team": "CLE",
        "opponent": "DET",
        "game_time": game_time,
        "captured_at_utc": "2026-08-18T12:00:00Z",
    }])


def test_prior_game_ids_are_strictly_before_target_date() -> None:
    assert prior_game_pks_from_payload(_game_log(), "2026-08-18", limit=2) == [110, 103]


def test_pitch_summary_filters_to_target_pitcher_and_typed_arsenal() -> None:
    counts, descriptions, raw, typed = extract_pitch_summary(_feed(55, ff=3, sl=2, unknown=1), 55)
    assert counts == {"FF": 3, "SL": 2}
    assert descriptions["FF"] == "Four-Seam Fastball"
    assert raw == 6
    assert typed == 5


def test_capture_freezes_prior_game_pitch_types_usage_and_timestamp() -> None:
    feeds = {110: _feed(55), 103: _feed(55, ff=12, sl=8)}
    result = build_capture_records(
        _projection(),
        captured_at=pd.Timestamp("2026-08-18T13:00:00Z"),
        recent_games_limit=2,
        game_log_resolver=lambda pitcher_id, season: _game_log(),
        feed_resolver=lambda game_pk: feeds[game_pk],
    )
    assert len(result) == 1
    row = result.iloc[0]
    assert row["source_game_pks"] == "110|103"
    assert row["arsenal_pitch_types"] == "FF|SL"
    usage = json.loads(row["arsenal_usage"])
    assert abs(float(usage["FF"]) - (36 / 56)) < 1e-6
    assert abs(float(usage["SL"]) - (20 / 56)) < 1e-6
    assert row["arsenal_captured_at_utc"].startswith("2026-08-18T13:00:00")
    assert row["audit_eligible"] in (True, 1)
    assert row["report_only"] in (True, 1)
    assert row["production_authority"] == "NONE"


def test_existing_frozen_capture_is_not_rewritten() -> None:
    first = build_capture_records(
        _projection(),
        captured_at=pd.Timestamp("2026-08-18T13:00:00Z"),
        game_log_resolver=lambda pitcher_id, season: _game_log(),
        feed_resolver=lambda game_pk: _feed(55),
    )
    second = build_capture_records(
        _projection(),
        first,
        captured_at=pd.Timestamp("2026-08-18T14:00:00Z"),
        game_log_resolver=lambda pitcher_id, season: _game_log(),
        feed_resolver=lambda game_pk: _feed(55, ff=50, sl=1),
    )
    assert len(second) == 1
    assert second.iloc[0]["arsenal_captured_at_utc"] == first.iloc[0]["arsenal_captured_at_utc"]
    assert second.iloc[0]["arsenal_usage"] == first.iloc[0]["arsenal_usage"]


def test_postgame_rows_are_never_captured() -> None:
    result = build_capture_records(
        _projection(game_time="2026-08-18T12:30:00Z"),
        captured_at=pd.Timestamp("2026-08-18T13:00:00Z"),
        game_log_resolver=lambda pitcher_id, season: _game_log(),
        feed_resolver=lambda game_pk: _feed(55),
    )
    assert result.empty


def test_low_typed_coverage_is_not_auditable() -> None:
    result = build_capture_records(
        _projection(),
        captured_at=pd.Timestamp("2026-08-18T13:00:00Z"),
        game_log_resolver=lambda pitcher_id, season: _game_log(),
        feed_resolver=lambda game_pk: _feed(55, ff=10, sl=10, unknown=10),
    )
    row = result.iloc[0]
    assert row["audit_eligible"] in (False, 0)
    assert "below the 90% capture floor" in row["reason"]


def test_contract_is_report_only() -> None:
    assert REPORT_ONLY is True
    assert PRODUCTION_AUTHORITY == "NONE"
    assert VERSION == "pitch-arsenal-capture-v1-report-only"
