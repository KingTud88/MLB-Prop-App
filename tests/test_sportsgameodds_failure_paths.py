from __future__ import annotations

import requests

import engine.sportsgameodds as sgo


class FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class InvalidJsonResponse(FakeResponse):
    def json(self):
        raise ValueError("synthetic invalid json")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers or {}),
                "params": dict(params or {}),
                "timeout": timeout,
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def _event(event_id: str) -> dict:
    player_id = f"PITCHER_{event_id}_MLB"
    odds = {}
    for stat, line in (("pitching_strikeouts", 6.5), ("pitching_outs", 17.5), ("pitching_hits", 5.5)):
        for side, price in (("over", -115), ("under", -105)):
            odds[f"{stat}-{player_id}-game-ou-{side}"] = {
                "oddID": f"{stat}-{player_id}-game-ou-{side}",
                "statID": stat,
                "statEntityID": player_id,
                "playerID": player_id,
                "periodID": "game",
                "betTypeID": "ou",
                "sideID": side,
                "byBookmaker": {
                    "espnbet": {
                        "odds": price,
                        "overUnder": line,
                        "available": True,
                    }
                },
            }
    return {
        "eventID": event_id,
        "leagueID": "MLB",
        "type": "match",
        "teams": {
            "home": {"names": {"long": "Detroit Tigers"}},
            "away": {"names": {"long": "Cleveland Guardians"}},
        },
        "players": {player_id: {"playerID": player_id, "name": f"Pitcher {event_id}"}},
        "status": {
            "started": False,
            "ended": False,
            "cancelled": False,
            "startsAt": "2026-08-19T23:10:00Z",
        },
        "odds": odds,
    }


def test_retryable_http_statuses_back_off_then_recover() -> None:
    sleeps = []
    session = FakeSession(
        [
            FakeResponse({}, status_code=429),
            FakeResponse({}, status_code=503),
            FakeResponse({"success": True, "data": [_event("evt-retry")], "nextCursor": None}),
        ]
    )

    offers, meta, error = sgo.fetch_slate_offers(
        "secret",
        "2026-08-19",
        session=session,
        sleep=sleeps.append,
    )

    assert error is None
    assert len(session.calls) == sgo.MAX_ATTEMPTS
    assert sleeps == list(sgo.BACKOFF_SECONDS)
    assert len(offers) == 6
    assert meta["pages"] == 1
    assert meta["event_count"] == 1


def test_connection_failures_exhaust_retries_and_fail_closed() -> None:
    sleeps = []
    session = FakeSession(
        [
            requests.ConnectionError("private one"),
            requests.ConnectionError("private two"),
            requests.ConnectionError("private three"),
        ]
    )

    offers, meta, error = sgo.fetch_slate_offers(
        "secret",
        "2026-08-19",
        session=session,
        sleep=sleeps.append,
    )

    assert offers.empty
    assert len(session.calls) == sgo.MAX_ATTEMPTS
    assert sleeps == list(sgo.BACKOFF_SECONDS)
    assert error == "SportsGameOdds temporarily unavailable after connection retries."
    assert meta["provider"] == sgo.PROVIDER
    assert meta["pages"] == 0
    assert meta["event_count"] == 0
    assert meta["error"] == error


def test_invalid_json_fails_closed_without_retrying() -> None:
    session = FakeSession([InvalidJsonResponse(None)])

    offers, meta, error = sgo.fetch_slate_offers(
        "secret",
        "2026-08-19",
        session=session,
        sleep=lambda _: None,
    )

    assert offers.empty
    assert len(session.calls) == 1
    assert error == "SportsGameOdds returned invalid JSON."
    assert meta["pages"] == 0
    assert meta["error"] == error


def test_success_false_fails_closed_without_using_payload_data() -> None:
    session = FakeSession(
        [FakeResponse({"success": False, "data": [_event("must-not-parse")], "nextCursor": None})]
    )

    offers, meta, error = sgo.fetch_slate_offers(
        "secret",
        "2026-08-19",
        session=session,
        sleep=lambda _: None,
    )

    assert offers.empty
    assert len(session.calls) == 1
    assert error == "SportsGameOdds returned success=false."
    assert meta["event_count"] == 0
    assert meta["error"] == error


def test_cursor_pagination_collects_multiple_pages() -> None:
    session = FakeSession(
        [
            FakeResponse({"success": True, "data": [_event("evt-one")], "nextCursor": "cursor-2"}),
            FakeResponse({"success": True, "data": [_event("evt-two")], "nextCursor": None}),
        ]
    )

    offers, meta, error = sgo.fetch_slate_offers(
        "secret",
        "2026-08-19",
        session=session,
        sleep=lambda _: None,
    )

    assert error is None
    assert len(session.calls) == 2
    assert "cursor" not in session.calls[0]["params"]
    assert session.calls[1]["params"]["cursor"] == "cursor-2"
    assert meta["pages"] == 2
    assert meta["event_count"] == 2
    assert len(offers) == 12
    assert set(offers["event_id"]) == {"evt-one", "evt-two"}


def test_pagination_safety_limit_fails_closed_instead_of_returning_partial_lines() -> None:
    responses = [
        FakeResponse(
            {
                "success": True,
                "data": [_event(f"evt-{page}")],
                "nextCursor": f"cursor-{page + 1}",
            }
        )
        for page in range(1, 6)
    ]
    session = FakeSession(responses)

    offers, meta, error = sgo.fetch_slate_offers(
        "secret",
        "2026-08-19",
        session=session,
        sleep=lambda _: None,
    )

    assert offers.empty
    assert len(session.calls) == 5
    assert meta["pages"] == 5
    assert meta["event_count"] == 5
    assert error == "SportsGameOdds pagination exceeded safety limit."
    assert meta["error"] == error
