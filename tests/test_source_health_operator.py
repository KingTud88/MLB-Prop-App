from __future__ import annotations

from pathlib import Path

import pytest
import requests

from runtime_http import (
    ExternalServiceError,
    _reset_source_health_for_tests,
    request_with_resilience,
    set_source_health_observer,
    source_health_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
ENGINE_INIT = ROOT / "engine" / "__init__.py"


class FakeResponse:
    def __init__(self, status_code: int = 200, payload=None):
        self.status_code = status_code
        self._payload = {} if payload is None else payload

    def json(self):
        return self._payload


def scripted(*outcomes):
    calls = []

    def _request(session, method, url, **kwargs):
        calls.append((method, url, kwargs))
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    return _request, calls


@pytest.fixture(autouse=True)
def reset_source_health():
    _reset_source_health_for_tests()
    yield
    _reset_source_health_for_tests()


def test_snapshot_starts_unchecked_and_is_defensive():
    initial = source_health_snapshot()
    assert [(row["service"], row["status"]) for row in initial] == [
        ("MLB data", "NOT CHECKED"),
        ("Weather data", "NOT CHECKED"),
    ]
    initial[0]["status"] = "MUTATED"
    assert source_health_snapshot()[0]["status"] == "NOT CHECKED"


def test_success_records_only_tracked_host_and_notifies_observer():
    events = []
    set_source_health_observer(lambda snapshot, host: events.append((snapshot, host)))
    request_func, calls = scripted(FakeResponse(200, {"dates": []}))

    response = request_with_resilience(
        requests.Session(),
        "GET",
        "https://statsapi.mlb.com/api/v1/schedule",
        request_func=request_func,
        sleep=lambda _: None,
    )

    assert response.status_code == 200
    assert len(calls) == 1
    snapshot = source_health_snapshot()
    assert snapshot[0]["status"] == "OK"
    assert snapshot[0]["last_path"] == "/api/v1/schedule"
    assert snapshot[0]["last_attempt_at_utc"]
    assert snapshot[0]["last_success_at_utc"]
    assert snapshot[0]["last_failure_at_utc"] is None
    assert snapshot[1]["status"] == "NOT CHECKED"
    assert events[-1][1] == "statsapi.mlb.com"
    assert events[-1][0][0]["status"] == "OK"


def test_failure_records_error_without_changing_safe_exception():
    request_func, calls = scripted(
        requests.ConnectionError("private one"),
        requests.ConnectionError("private two"),
        requests.ConnectionError("private three"),
    )

    with pytest.raises(ExternalServiceError) as exc_info:
        request_with_resilience(
            requests.Session(),
            "GET",
            "https://api.open-meteo.com/v1/forecast",
            request_func=request_func,
            sleep=lambda _: None,
        )

    assert len(calls) == 3
    assert str(exc_info.value) == "Weather data temporarily unavailable. Please try again."
    snapshot = source_health_snapshot()
    assert snapshot[0]["status"] == "NOT CHECKED"
    assert snapshot[1]["status"] == "ERROR"
    assert snapshot[1]["last_path"] == "/v1/forecast"
    assert snapshot[1]["last_failure_at_utc"]
    assert snapshot[1]["last_success_at_utc"] is None


def test_observer_failure_cannot_change_request_semantics():
    def broken_observer(snapshot, host):
        raise RuntimeError("presentation broke")

    set_source_health_observer(broken_observer)
    request_func, _ = scripted(FakeResponse(200, {"ok": True}))
    response = request_with_resilience(
        requests.Session(),
        "GET",
        "https://api.open-meteo.com/v1/forecast",
        request_func=request_func,
        sleep=lambda _: None,
    )
    assert response.status_code == 200
    assert source_health_snapshot()[1]["status"] == "OK"


def test_untracked_host_remains_passthrough_and_unobserved():
    before = source_health_snapshot()
    request_func, calls = scripted(FakeResponse(503, {"book": "unchanged"}))
    returned = request_with_resilience(
        requests.Session(),
        "GET",
        "https://example.com/api",
        request_func=request_func,
        sleep=lambda _: pytest.fail("untracked request must not sleep"),
    )
    assert returned.status_code == 503
    assert len(calls) == 1
    assert source_health_snapshot() == before


def test_sidebar_contract_is_operator_only_and_schedule_anchored():
    source = ENGINE_INIT.read_text(encoding="utf-8")
    assert "set_source_health_observer as _set_source_health_observer" in source
    assert "_set_source_health_observer(_render_source_health)" in source
    assert 'event_host == "statsapi.mlb.com"' in source
    assert '== "/api/v1/schedule"' in source
    assert "_st.sidebar.empty()" in source
    assert '_original_markdown("#### SOURCE HEALTH")' in source
    assert '_st.caption(f"{service}: {status} · {checked}")' in source


def test_sidebar_source_health_slot_is_created_once_per_session():
    source = ENGINE_INIT.read_text(encoding="utf-8")
    assert "and session_id not in _source_health_slots" in source
    assert source.count("_st.sidebar.empty()") == 1
