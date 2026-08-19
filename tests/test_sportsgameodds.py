from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

import engine.sportsgameodds as sgo


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append({"url": url, "headers": dict(headers or {}), "params": dict(params or {}), "timeout": timeout})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _event(*, started=False, include_espn=True, espn_same_line=True, notice=None):
    players = {
        "TARIK_SKUBAL_1_MLB": {"playerID": "TARIK_SKUBAL_1_MLB", "name": "Tarik Skubal"},
    }
    odds = {}
    for stat, line in (("pitching_strikeouts", 6.5), ("pitching_outs", 17.5), ("pitching_hits", 5.5)):
        for side, price in (("over", -115), ("under", -105)):
            by_book = {
                "fanduel": {"odds": price - 2, "overUnder": line, "available": True, "lastUpdatedAt": "2026-08-19T16:00:00Z"},
                "draftkings": {"odds": price - 4, "overUnder": line, "available": True},
            }
            if include_espn:
                espn_line = line if espn_same_line or side == "over" else line + 1.0
                by_book["espnbet"] = {"odds": price, "overUnder": espn_line, "available": True, "deeplink": "https://example.invalid"}
            odds[f"{stat}-TARIK_SKUBAL_1_MLB-game-ou-{side}"] = {
                "oddID": f"{stat}-TARIK_SKUBAL_1_MLB-game-ou-{side}",
                "statID": stat,
                "statEntityID": "TARIK_SKUBAL_1_MLB",
                "playerID": "TARIK_SKUBAL_1_MLB",
                "periodID": "game",
                "betTypeID": "ou",
                "sideID": side,
                "fairOverUnder": str(line - 2.0),
                "bookOverUnder": str(line - 1.0),
                "byBookmaker": by_book,
            }
    return {
        "eventID": "evt1",
        "leagueID": "MLB",
        "type": "match",
        "teams": {
            "home": {"names": {"long": "Detroit Tigers"}},
            "away": {"names": {"long": "Cleveland Guardians"}},
        },
        "players": players,
        "status": {
            "started": started,
            "ended": False,
            "cancelled": False,
            "startsAt": "2026-08-19T23:10:00Z",
        },
        "odds": odds,
    }


def test_fetch_requests_only_mlb_pitcher_markets_and_preserves_notice():
    session = FakeSession([FakeResponse({"success": True, "data": [_event()], "nextCursor": None, "notice": "free-tier filter active"})])
    offers, meta, error = sgo.fetch_slate_offers("secret", "2026-08-19", session=session, sleep=lambda _: None)
    assert error is None
    assert len(offers) == 18
    assert set(offers["market"]) == {"pitcher_strikeouts", "pitcher_outs", "pitcher_hits_allowed"}
    assert meta["notice"] == "free-tier filter active"
    call = session.calls[0]
    assert call["headers"]["x-api-key"] == "secret"
    assert call["params"]["leagueID"] == "MLB"
    assert call["params"]["started"] == "false"
    assert call["params"]["includeAltLines"] == "false"
    assert "pitching_strikeouts-PLAYER_ID-game-ou-over" in call["params"]["oddID"]
    assert "pitching_outs-PLAYER_ID-game-ou-over" in call["params"]["oddID"]
    assert "pitching_hits-PLAYER_ID-game-ou-over" in call["params"]["oddID"]


def test_preferred_pairs_use_espn_bet_and_never_consensus_values():
    session = FakeSession([FakeResponse({"success": True, "data": [_event()], "nextCursor": None})])
    offers, _, _ = sgo.fetch_slate_offers("secret", "2026-08-19", session=session, sleep=lambda _: None)
    selected = sgo.select_preferred_book_pairs(offers)
    assert len(selected) == 6
    assert set(selected["bookmaker_id"]) == {"espnbet"}
    assert set(selected.loc[selected["market"].eq("pitcher_strikeouts"), "point"]) == {6.5}
    assert set(selected.loc[selected["market"].eq("pitcher_outs"), "point"]) == {17.5}
    assert set(selected.loc[selected["market"].eq("pitcher_hits_allowed"), "point"]) == {5.5}


def test_mismatched_espn_pair_falls_back_to_complete_real_book_pair():
    session = FakeSession([FakeResponse({"success": True, "data": [_event(espn_same_line=False)], "nextCursor": None})])
    offers, _, _ = sgo.fetch_slate_offers("secret", "2026-08-19", session=session, sleep=lambda _: None)
    selected = sgo.select_preferred_book_pairs(offers)
    assert len(selected) == 6
    assert set(selected["bookmaker_id"]) == {"fanduel"}


def test_unavailable_or_started_markets_do_not_become_active_lines():
    event = _event(started=True)
    session = FakeSession([FakeResponse({"success": True, "data": [event], "nextCursor": None})])
    offers, _, error = sgo.fetch_slate_offers("secret", "2026-08-19", session=session, sleep=lambda _: None)
    assert error is None
    assert offers.empty
    assert sgo.select_preferred_book_pairs(offers).empty


def test_missing_key_fails_without_network_call():
    session = FakeSession([])
    offers, meta, error = sgo.fetch_slate_offers("", "2026-08-19", session=session, sleep=lambda _: None)
    assert offers.empty
    assert meta == {}
    assert "not configured" in error
    assert session.calls == []


def test_projection_log_overlay_preserves_manual_and_sets_all_three_real_lines():
    session = FakeSession([FakeResponse({"success": True, "data": [_event()], "nextCursor": None})])
    offers, _, _ = sgo.fetch_slate_offers("secret", "2026-08-19", session=session, sleep=lambda _: None)
    selected = sgo.select_preferred_book_pairs(offers)
    log = pd.DataFrame([
        {
            "game_date": "2026-08-19", "player": "Tarik Skubal",
            "active_strikeout_line": 7.5, "active_strikeout_line_source": "MANUAL",
            "active_outs_line": None, "active_outs_line_source": "",
            "active_hits_allowed_line": None, "active_hits_allowed_line_source": "",
        }
    ])
    updated, applied = sgo.apply_selected_lines_to_projection_log(log, selected, "2026-08-19")
    assert applied == 2
    row = updated.iloc[0]
    assert row["active_strikeout_line"] == 7.5
    assert row["active_strikeout_line_source"] == "MANUAL"
    assert row["active_outs_line"] == 17.5
    assert row["active_hits_allowed_line"] == 5.5
    assert row["active_outs_line_source"] == "SPORTSGAMEODDS · ESPN BET"
    assert row["active_hits_allowed_line_source"] == "SPORTSGAMEODDS · ESPN BET"


def test_disk_loader_fails_closed_when_snapshot_is_stale(tmp_path):
    path = tmp_path / "snapshot.csv"
    now = datetime(2026, 8, 19, 18, 0, tzinfo=timezone.utc)
    row = {
        "slate_date": "2026-08-19", "event_id": "evt1", "commence_time": "2026-08-19T23:10:00+00:00",
        "home_team": "DET", "away_team": "CLE", "player_id": "TARIK_SKUBAL_1_MLB", "pitcher": "Tarik Skubal",
        "market": "pitcher_strikeouts", "side": "Over", "point": 6.5, "price": -115,
        "bookmaker_id": "espnbet", "book": "ESPN BET", "provider": sgo.PROVIDER,
        "book_last_updated_at": "", "deeplink": "", "fetched_at_utc": (now - timedelta(hours=7)).isoformat(),
    }
    pd.DataFrame([row], columns=sgo.OFFER_COLUMNS).to_csv(path, index=False)
    assert sgo.load_pitcher_market_odds("Tarik Skubal", "2026-08-19", snapshot_path=path, now_utc=now) == []
    fresh = pd.DataFrame([{**row, "fetched_at_utc": (now - timedelta(hours=1)).isoformat()}], columns=sgo.OFFER_COLUMNS)
    fresh.to_csv(path, index=False)
    loaded = sgo.load_pitcher_market_odds("Tarik Skubal", "2026-08-19", snapshot_path=path, now_utc=now)
    assert len(loaded) == 1
    assert loaded[0]["provider"] == sgo.PROVIDER
