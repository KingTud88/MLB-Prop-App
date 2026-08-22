from types import SimpleNamespace

import pandas as pd

from training.outs_opponent_pressure_capture import (
    LEAGUE_K_RATE,
    LEAGUE_OBP,
    _obp_from_stat,
    build_capture_records,
    summarize_pressure,
)


def test_obp_uses_direct_value_or_standard_components():
    assert _obp_from_stat({"onBasePercentage": ".345"}) == 0.345
    derived = _obp_from_stat({"hits": 30, "baseOnBalls": 10, "hitByPitch": 2, "atBats": 100, "sacFlies": 3})
    assert abs(derived - (42 / 115)) < 1e-12


def test_confirmed_lineup_summary_shrinks_each_hitter_before_averaging():
    batters = pd.DataFrame([
        {"Batter": "A", "PA": 120, "K_Rate": .18, "OBP": .360, "Split_Available": True},
        {"Batter": "B", "PA": 0, "K_Rate": LEAGUE_K_RATE, "OBP": LEAGUE_OBP, "Split_Available": False},
    ])
    summary = summarize_pressure(batters, confirmed_lineup=True)
    expected_k_a = (.18 * 120 + LEAGUE_K_RATE * 60) / 180
    expected_obp_a = (.360 * 120 + LEAGUE_OBP * 60) / 180
    assert abs(summary["opponent_k_rate"] - ((expected_k_a + LEAGUE_K_RATE) / 2)) < 1e-12
    assert abs(summary["opponent_obp"] - ((expected_obp_a + LEAGUE_OBP) / 2)) < 1e-12
    assert summary["split_coverage"] == .5


def test_capture_is_future_only_pregame_and_preserves_confirmed_lineup_hash():
    projections = pd.DataFrame([
        {"game_date": "2026-08-22", "game_pk": 1, "pitcher_id": 11, "player": "Old", "team": "CLE", "opponent": "NYY", "opponent_team_id": 147, "game_time": "2026-08-22T23:00:00Z", "captured_at_utc": "2026-08-22T12:00:00Z", "lineup_source": "ACTIVE_ROSTER", "lineup_confirmed": False, "lineup_hash": ""},
        {"game_date": "2026-08-23", "game_pk": 2, "pitcher_id": 22, "player": "Future", "team": "CLE", "opponent": "NYY", "opponent_team_id": 147, "game_time": "2026-08-23T23:00:00Z", "captured_at_utc": "2026-08-23T12:00:00Z", "lineup_source": "CONFIRMED_LINEUP", "lineup_confirmed": True, "lineup_hash": "abc", "opponent_k_pct": 21.0, "opponent_hit_rate": .24},
    ])
    lineup = SimpleNamespace(confirmed=True, fingerprint="abc", player_ids=(101, 102))
    batters = pd.DataFrame([
        {"Batter": "A", "PA": 100, "K_Rate": .19, "OBP": .350, "Split_Available": True},
        {"Batter": "B", "PA": 80, "K_Rate": .20, "OBP": .340, "Split_Available": True},
    ])
    result = build_capture_records(
        projections,
        captured_at=pd.Timestamp("2026-08-23T18:00:00Z"),
        hand_resolver=lambda _: "R",
        lineup_resolver=lambda *_: lineup,
        batters_resolver=lambda *_: batters,
    )
    assert len(result) == 1
    row = result.iloc[0]
    assert int(row["game_pk"]) == 2
    assert row["lineage"] == "PRE_GAME_CONFIRMED_MATCH"
    assert bool(row["audit_eligible"])
    assert row["production_authority"] == "NONE"
    assert float(row["opponent_obp"]) > .32
    assert float(row["opponent_contact_rate"]) > .79


def test_confirmed_hash_mismatch_fails_closed():
    projections = pd.DataFrame([{
        "game_date": "2026-08-23", "game_pk": 2, "pitcher_id": 22, "player": "Future",
        "team": "CLE", "opponent": "NYY", "opponent_team_id": 147,
        "game_time": "2026-08-23T23:00:00Z", "captured_at_utc": "2026-08-23T12:00:00Z",
        "lineup_source": "CONFIRMED_LINEUP", "lineup_confirmed": True, "lineup_hash": "frozen",
    }])
    lineup = SimpleNamespace(confirmed=True, fingerprint="different", player_ids=(101,))
    result = build_capture_records(
        projections,
        captured_at=pd.Timestamp("2026-08-23T18:00:00Z"),
        hand_resolver=lambda _: "R",
        lineup_resolver=lambda *_: lineup,
        batters_resolver=lambda *_: pd.DataFrame(),
    )
    row = result.iloc[0]
    assert not bool(row["audit_eligible"])
    assert row["lineage"] == "CONFIRMED_LINEUP_HASH_MISMATCH"
