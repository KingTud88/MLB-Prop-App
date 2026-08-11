from __future__ import annotations

import pandas as pd

from training.bet_storage import append_bet, bet_row_key, delete_bet, load_bet_log


def test_delete_bet_removes_exact_saved_ticket(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    path = tmp_path / "bets.csv"
    first = {
        "player": "Pitcher A",
        "market": "Strikeouts",
        "game_date": "2026-08-11",
        "line": 5.5,
        "side": "Over",
        "entered_at_utc": "2026-08-11T17:00:00Z",
    }
    second = {
        "player": "Pitcher B",
        "market": "Total Outs",
        "game_date": "2026-08-11",
        "line": 17.5,
        "side": "Under",
        "entered_at_utc": "2026-08-11T17:01:00Z",
    }
    append_bet(path, first)
    append_bet(path, second)

    saved = load_bet_log(path)
    assert len(saved) == 2
    assert "bet_id" in saved.columns
    key = bet_row_key(saved.iloc[0])

    assert delete_bet(path, key) is True
    remaining = load_bet_log(path)
    assert len(remaining) == 1
    assert remaining.iloc[0]["player"] == "Pitcher B"
    assert delete_bet(path, key) is False


def test_legacy_ticket_without_bet_id_can_be_deleted(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    path = tmp_path / "legacy.csv"
    frame = pd.DataFrame([
        {
            "player": "5-leg parlay",
            "bet_type": "Parlay",
            "market": "Parlay",
            "game_date": "2026-08-11",
            "entered_at_utc": "2026-08-11T17:30:00Z",
            "parlay_legs": '[{"player":"A"},{"player":"B"}]',
            "source": "Top Plays Model Parlay",
            "book": "FanDuel",
        }
    ])
    frame.to_csv(path, index=False)
    key = bet_row_key(frame.iloc[0])
    assert key.startswith("legacy:")
    assert delete_bet(path, key) is True
    assert load_bet_log(path).empty
