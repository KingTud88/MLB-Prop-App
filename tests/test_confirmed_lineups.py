from __future__ import annotations

import pandas as pd

from engine.lineup_context import LINEUP_ACTIVE_ROSTER, LINEUP_CONFIRMED, get_confirmed_lineup, lineup_fingerprint
from engine.opposing_batters import LEAGUE_HIT_RATE, LEAGUE_K_RATE, matchup_summary


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
    def raise_for_status(self):
        return None
    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
    def get(self, *args, **kwargs):
        return FakeResponse(self.payload)


def test_confirmed_lineup_parser_keeps_batting_order():
    ids = list(range(101, 110))
    payload = {
        "teams": {
            "away": {"team": {"id": 142}, "battingOrder": ids},
            "home": {"team": {"id": 139}, "battingOrder": list(range(201, 210))},
        }
    }
    ctx = get_confirmed_lineup(999, 142, session=FakeSession(payload))
    assert ctx.source == LINEUP_CONFIRMED
    assert ctx.confirmed is True
    assert ctx.player_ids == tuple(ids)
    assert ctx.spots[0] == (101, 1)
    assert ctx.spots[-1] == (109, 9)
    assert ctx.fingerprint == lineup_fingerprint(tuple(ids))


def test_incomplete_lineup_stays_roster_fallback():
    payload = {"teams": {"away": {"team": {"id": 142}, "battingOrder": [1, 2, 3]}}}
    ctx = get_confirmed_lineup(999, 142, session=FakeSession(payload))
    assert ctx.source == LINEUP_ACTIVE_ROSTER
    assert ctx.confirmed is False
    assert ctx.player_ids == ()


def test_confirmed_summary_uses_all_hitters_with_split_shrinkage_and_contact():
    batters = pd.DataFrame({
        "Batter": [f"B{i}" for i in range(9)],
        "K% vs Pitcher": [0.40] + [0.20] * 8,
        "H/PA vs Pitcher": [0.10] + [0.25] * 8,
        "PA": [1000.0] + [20.0] * 8,
        "Risk": ["HIGH"] + ["NORMAL"] * 8,
    })
    active = matchup_summary(batters, confirmed_lineup=False)
    confirmed = matchup_summary(batters, confirmed_lineup=True)
    assert active["k_rate"] > confirmed["k_rate"]
    assert confirmed["k_rate"] > LEAGUE_K_RATE * 0.8
    assert 0.12 <= confirmed["hit_rate"] <= 0.36
    assert confirmed["hit_rate"] != LEAGUE_HIT_RATE
