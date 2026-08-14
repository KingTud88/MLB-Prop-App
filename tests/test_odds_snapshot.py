from __future__ import annotations

from pathlib import Path

import pandas as pd

import engine.odds_snapshot as odds


class FakeResponse:
    def __init__(self, payload, headers=None):
        self._payload = payload
        self.headers = headers or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        if url.endswith("/events"):
            return FakeResponse([
                {
                    "id": "evt1",
                    "commence_time": "2026-08-14T23:10:00Z",
                    "home_team": "Cleveland Guardians",
                    "away_team": "Atlanta Braves",
                }
            ])
        return FakeResponse(
            {
                "bookmakers": [
                    {
                        "title": "ExampleBook",
                        "markets": [
                            {
                                "key": "pitcher_strikeouts",
                                "outcomes": [
                                    {"description": "Chris Sale", "name": "Over", "point": 6.5, "price": -110},
                                    {"description": "Chris Sale", "name": "Under", "point": 6.5, "price": -120},
                                ],
                            }
                        ],
                    }
                ]
            },
            headers={"x-requests-last": "1", "x-requests-remaining": "99", "x-requests-used": "1"},
        )


def test_refresh_requests_only_main_strikeout_market(tmp_path, monkeypatch):
    monkeypatch.setattr(odds, "SNAPSHOT_PATH", tmp_path / "odds.csv")
    session = FakeSession()
    frame, quota, error = odds.refresh_strikeout_snapshot("secret", "2026-08-14", session=session)
    assert error is None
    assert len(frame) == 2
    assert set(frame["market"]) == {"pitcher_strikeouts"}
    prop_calls = [params for url, params in session.calls if "/odds" in url]
    assert prop_calls and all(params.get("markets") == "pitcher_strikeouts" for params in prop_calls)
    assert quota["last"] == 1


def test_main_page_loader_is_disk_only(tmp_path, monkeypatch):
    path = tmp_path / "odds.csv"
    monkeypatch.setattr(odds, "SNAPSHOT_PATH", path)
    pd.DataFrame([
        {
            "slate_date": "2026-08-14", "event_id": "evt1", "commence_time": "", "home_team": "",
            "away_team": "", "pitcher": "Chris Sale", "book": "ExampleBook", "market": "pitcher_strikeouts",
            "name": "Over", "point": 6.5, "price": -110, "fetched_at_utc": "now",
        }
    ]).to_csv(path, index=False)
    rows = odds.load_pitcher_strikeout_odds("  Chris   Sale ", "2026-08-14")
    assert rows == [{"book": "ExampleBook", "market": "pitcher_strikeouts", "name": "Over", "point": 6.5, "price": -110.0}]
