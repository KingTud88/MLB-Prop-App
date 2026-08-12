from __future__ import annotations

import pandas as pd

import automation.daily_projection_runner as runner
import automation.resolve_projection_log as resolver


def _row() -> dict:
    return {
        "game_pk": 12345,
        "game_date": "2026-08-12",
        "pitcher_id": 987,
        "player": "History Only Pitcher",
        "team": "CLE",
        "opponent": "DET",
        "venue": "Test Park",
        "game_time": "2026-08-12T23:10:00Z",
    }


def _live_feed() -> dict:
    return {
        "gameData": {"status": {"abstractGameState": "Final"}},
        "liveData": {
            "boxscore": {
                "teams": {
                    "away": {
                        "players": {
                            "ID987": {
                                "stats": {
                                    "pitching": {
                                        "strikeOuts": 6,
                                        "hits": 4,
                                        "inningsPitched": "5.2",
                                        "battersFaced": 23,
                                        "numberOfPitches": 91,
                                    }
                                }
                            }
                        }
                    },
                    "home": {"players": {}},
                }
            }
        },
    }


def test_history_only_record_is_separate_and_deduplicated(tmp_path, monkeypatch):
    path = tmp_path / "starter_observation_log.csv"
    monkeypatch.setattr(runner, "OBS_LOG_PATH", path)

    assert runner.record_history_only(_row()) is True
    assert runner.record_history_only(_row()) is False

    frame = runner.load_observation_log()
    assert len(frame) == 1
    assert frame.loc[0, "reason"] == "no usable starter history"
    assert frame.loc[0, "history_semantics"] == runner.HISTORY_SEMANTICS
    assert "projection" not in frame.columns
    assert "sim_5p" not in frame.columns


def test_resolved_observation_becomes_fallback_starter_history(tmp_path, monkeypatch):
    path = tmp_path / "starter_observation_log.csv"
    monkeypatch.setattr(runner, "OBS_LOG_PATH", path)
    runner.record_history_only(_row())
    frame = runner.load_observation_log()
    frame.loc[0, "actual_strikeouts"] = 6
    frame.loc[0, "actual_hits_allowed"] = 4
    frame.loc[0, "actual_outs"] = 17
    frame.loc[0, "actual_batters_faced"] = 23
    frame.loc[0, "actual_pitches"] = 91
    frame.loc[0, "resolved_at_utc"] = "2026-08-13T03:00:00+00:00"
    runner.save_observation_log(frame)

    history = runner.observation_history(987)
    assert len(history) == 1
    assert history.loc[0, "k"] == 6
    assert history.loc[0, "hits"] == 4
    assert history.loc[0, "outs"] == 17
    assert history.loc[0, "bf"] == 23
    assert history.loc[0, "pitches"] == 91
    assert history.loc[0, "games_started"] == 1


def test_observation_is_not_double_counted_when_mlb_log_has_same_date(tmp_path, monkeypatch):
    path = tmp_path / "starter_observation_log.csv"
    monkeypatch.setattr(runner, "OBS_LOG_PATH", path)
    runner.record_history_only(_row())
    frame = runner.load_observation_log()
    frame.loc[0, "actual_strikeouts"] = 6
    frame.loc[0, "actual_hits_allowed"] = 4
    frame.loc[0, "actual_outs"] = 17
    frame.loc[0, "actual_batters_faced"] = 23
    frame.loc[0, "actual_pitches"] = 91
    runner.save_observation_log(frame)

    mlb_log = pd.DataFrame([
        {
            "date": pd.Timestamp("2026-08-12"),
            "bf": 23.0,
            "k": 6.0,
            "hits": 4.0,
            "pitches": 91.0,
            "outs": 17.0,
            "games_started": 1,
        }
    ])
    merged = runner.supplement_with_observations(mlb_log, 987)
    assert len(merged) == 1


def test_runner_routes_boxscore_reads_through_v11_live_feed(monkeypatch):
    called = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return _live_feed()

    def fake_get(url, params=None, timeout=None):
        called["url"] = url
        return Response()

    monkeypatch.setattr(runner.SESSION, "get", fake_get)
    data = runner.get_json("game/12345/boxscore", {})
    assert called["url"] == "https://statsapi.mlb.com/api/v1.1/game/12345/feed/live"
    assert data["gameData"]["status"]["abstractGameState"] == "Final"
    assert "ID987" in data["teams"]["away"]["players"]


def test_history_observation_resolver_captures_full_pitching_line(monkeypatch):
    shaped = {
        "gameData": _live_feed()["gameData"],
        "teams": _live_feed()["liveData"]["boxscore"]["teams"],
    }
    monkeypatch.setattr(runner, "get_json", lambda endpoint, params: shaped)
    result = runner.resolve_observation_row(pd.Series(_row()))
    assert result["actual_strikeouts"] == 6
    assert result["actual_hits_allowed"] == 4
    assert result["actual_outs"] == 17
    assert result["actual_batters_faced"] == 23
    assert result["actual_pitches"] == 91


def test_projection_resolver_routes_boxscore_reads_through_v11_live_feed(monkeypatch):
    called = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return _live_feed()

    def fake_get(url, params=None, timeout=None):
        called["url"] = url
        return Response()

    monkeypatch.setattr(resolver.SESSION, "get", fake_get)
    data = resolver.get_json("game/12345/boxscore")
    assert called["url"] == "https://statsapi.mlb.com/api/v1.1/game/12345/feed/live"
    assert data["gameData"]["status"]["abstractGameState"] == "Final"
