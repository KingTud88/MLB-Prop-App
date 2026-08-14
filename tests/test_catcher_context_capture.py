from __future__ import annotations

import pandas as pd

from training.catcher_context_capture import build_capture, parse_starting_catcher


def _payload() -> dict:
    return {
        "teams": {
            "away": {
                "team": {"id": 144},
                "players": {
                    "ID1": {
                        "person": {"id": 1, "fullName": "Starting Catcher"},
                        "position": {"abbreviation": "C"},
                        "battingOrder": "700",
                    },
                    "ID2": {
                        "person": {"id": 2, "fullName": "Backup Catcher"},
                        "position": {"abbreviation": "C"},
                    },
                },
            },
            "home": {"team": {"id": 109}, "players": {}},
        }
    }


def test_parse_starting_catcher_requires_batting_order() -> None:
    catcher = parse_starting_catcher(_payload(), 144)
    assert catcher["catcher_id"] == 1
    assert catcher["catcher_name"] == "Starting Catcher"
    assert catcher["catcher_confirmed"] is True


def test_parse_starting_catcher_does_not_use_backup() -> None:
    payload = _payload()
    del payload["teams"]["away"]["players"]["ID1"]
    assert parse_starting_catcher(payload, 144) == {}


def test_build_capture_preserves_first_confirmed_catcher(monkeypatch) -> None:
    projections = pd.DataFrame([
        {
            "game_date": "2026-08-14", "game_pk": 10, "pitcher_id": 20,
            "player": "Pitcher", "team": "ATL", "team_id": 144,
            "captured_at_utc": "2026-08-14T15:00:00+00:00",
            "actual_strikeouts": 6, "actual_pitches": 92,
            "actual_batters_faced": 24, "actual_outs": 18,
        }
    ])
    existing = pd.DataFrame([
        {
            "game_pk": 10, "pitcher_id": 20, "catcher_id": 99,
            "catcher_name": "Pregame Catcher", "catcher_confirmed": True,
            "catcher_source": "MLB_POSTED_LINEUP",
            "catcher_captured_at_utc": "2026-08-14T14:30:00+00:00",
        }
    ])

    def should_not_fetch(*args, **kwargs):
        raise AssertionError("confirmed catcher should remain immutable")

    monkeypatch.setattr("training.catcher_context_capture.fetch_starting_catcher", should_not_fetch)
    out = build_capture(projections, existing)
    row = out.iloc[0]
    assert int(row["catcher_id"]) == 99
    assert row["catcher_name"] == "Pregame Catcher"
    assert row["candidate_authority"] == "REPORT_ONLY"
    assert float(row["catcher_factor"]) == 1.0
