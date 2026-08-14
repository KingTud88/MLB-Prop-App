from __future__ import annotations

import pandas as pd

from engine.umpire_context import (
    FACTOR_CAP_HIGH,
    FACTOR_CAP_LOW,
    candidate_from_prior,
    extract_home_plate_umpire,
    resolved_game_observation,
)


def _feed(state: str = "Final") -> dict:
    return {
        "gameData": {"status": {"abstractGameState": state}},
        "liveData": {
            "boxscore": {
                "officials": [
                    {"official": {"id": 999, "fullName": "Test Ump"}, "officialType": "Home Plate"},
                    {"official": {"id": 998, "fullName": "Other Ump"}, "officialType": "First Base"},
                ],
                "teams": {
                    "away": {"teamStats": {"pitching": {"strikeOuts": 8, "battersFaced": 36}}},
                    "home": {"teamStats": {"pitching": {"strikeOuts": 10, "battersFaced": 38}}},
                },
            }
        },
    }


def test_extracts_only_home_plate_umpire() -> None:
    assert extract_home_plate_umpire(_feed()) == {"umpire_id": 999, "umpire_name": "Test Ump"}


def test_final_observation_uses_both_team_pitching_totals() -> None:
    row = resolved_game_observation(_feed(), 123, "2026-08-01")
    assert row is not None
    assert row["total_strikeouts"] == 18.0
    assert row["total_batters_faced"] == 74.0
    assert abs(float(row["game_k_rate"]) - 18 / 74) < 1e-12
    assert resolved_game_observation(_feed("Live"), 123, "2026-08-01") is None


def test_candidate_excludes_same_day_and_future_games() -> None:
    history = pd.DataFrame([
        {"game_date": "2026-07-01", "umpire_id": 999, "total_strikeouts": 20, "total_batters_faced": 70},
        {"game_date": "2026-08-10", "umpire_id": 999, "total_strikeouts": 40, "total_batters_faced": 70},
        {"game_date": "2026-08-11", "umpire_id": 999, "total_strikeouts": 50, "total_batters_faced": 70},
    ])
    result = candidate_from_prior(history, 999, "2026-08-10")
    assert result["umpire_prior_games"] == 1
    assert abs(float(result["umpire_prior_k_rate"]) - 20 / 70) < 1e-12
    assert result["umpire_candidate_status"] == "LEARNING"
    assert result["umpire_k_factor_candidate"] == 1.0


def test_candidate_requires_20_prior_games_then_shrinks_and_caps() -> None:
    rows = []
    for day in range(1, 21):
        rows.append({
            "game_date": f"2026-07-{day:02d}",
            "umpire_id": 999,
            "total_strikeouts": 24,
            "total_batters_faced": 70,
        })
        rows.append({
            "game_date": f"2026-07-{day:02d}",
            "umpire_id": 555,
            "total_strikeouts": 8,
            "total_batters_faced": 70,
        })
    history = pd.DataFrame(rows)
    result = candidate_from_prior(history, 999, "2026-08-01")
    assert result["umpire_prior_games"] == 20
    assert result["umpire_candidate_status"] == "AUDITABLE"
    factor = float(result["umpire_k_factor_candidate"])
    assert FACTOR_CAP_LOW <= factor <= FACTOR_CAP_HIGH
    assert factor > 1.0
