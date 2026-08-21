from __future__ import annotations

import base64

from training import bet_storage


class _Response:
    def __init__(self, *, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _payload(csv_text: str, sha: str = "saved-sha") -> dict[str, str]:
    return {
        "content": base64.b64encode(csv_text.encode("utf-8")).decode("ascii"),
        "sha": sha,
    }


def test_github_load_reads_bet_data_branch(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    seen = {}

    def fake_get(url, **kwargs):
        seen["url"] = url
        seen["kwargs"] = kwargs
        return _Response(payload=_payload("player,bet_id\nPitcher A,abc\n"))

    monkeypatch.setattr(bet_storage.requests, "get", fake_get)
    frame = bet_storage.load_bet_log(tmp_path / "unused.csv")

    assert frame.iloc[0]["player"] == "Pitcher A"
    assert seen["kwargs"]["params"] == {"ref": "bet-data"}
    assert bet_storage.BET_LOG_BRANCH == "bet-data"


def test_github_append_writes_bet_data_branch_not_main(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    seen = {"puts": []}

    def fake_get(url, **kwargs):
        seen["get_kwargs"] = kwargs
        return _Response(payload=_payload("player,bet_id\nPitcher A,abc\n"))

    def fake_put(url, **kwargs):
        seen["puts"].append(kwargs)
        return _Response(status_code=200)

    monkeypatch.setattr(bet_storage.requests, "get", fake_get)
    monkeypatch.setattr(bet_storage.requests, "put", fake_put)

    bet_storage.append_bet(tmp_path / "unused.csv", {"player": "Pitcher B"})

    assert seen["get_kwargs"]["params"] == {"ref": "bet-data"}
    body = seen["puts"][0]["json"]
    assert body["branch"] == "bet-data"
    assert body["branch"] != "main"
    assert body["sha"] == "saved-sha"


def test_github_delete_reads_and_writes_bet_data_branch(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    seen = {"puts": []}
    csv_text = "player,bet_id\nPitcher A,abc\nPitcher B,def\n"

    def fake_get(url, **kwargs):
        seen["get_kwargs"] = kwargs
        return _Response(payload=_payload(csv_text))

    def fake_put(url, **kwargs):
        seen["puts"].append(kwargs)
        return _Response(status_code=200)

    monkeypatch.setattr(bet_storage.requests, "get", fake_get)
    monkeypatch.setattr(bet_storage.requests, "put", fake_put)

    assert bet_storage.delete_bet(tmp_path / "unused.csv", "id:abc") is True
    assert seen["get_kwargs"]["params"] == {"ref": "bet-data"}
    body = seen["puts"][0]["json"]
    assert body["branch"] == "bet-data"
    assert body["branch"] != "main"
    decoded = base64.b64decode(body["content"]).decode("utf-8")
    assert "Pitcher A" not in decoded
    assert "Pitcher B" in decoded
