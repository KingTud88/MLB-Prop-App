from __future__ import annotations

import requests
import pytest

from runtime_http import (
    BACKOFF_SECONDS,
    ExternalServiceError,
    MAX_ATTEMPTS,
    request_with_resilience,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, json_error=None):
        self.status_code = status_code
        self._payload = {} if payload is None else payload
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
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


def test_retries_transient_mlb_status_then_returns_success():
    request_func, calls = scripted(FakeResponse(503), FakeResponse(200, {"dates": []}))
    sleeps = []

    response = request_with_resilience(
        requests.Session(),
        "GET",
        "https://statsapi.mlb.com/api/v1/schedule",
        request_func=request_func,
        sleep=sleeps.append,
        timeout=20,
    )

    assert response.status_code == 200
    assert len(calls) == 2
    assert sleeps == [BACKOFF_SECONDS[0]]
    assert calls[0][2]["timeout"] == 20


def test_retries_connection_errors_then_exposes_only_safe_public_message():
    request_func, calls = scripted(
        requests.ConnectionError("socket detail 123"),
        requests.ConnectionError("socket detail 456"),
        requests.ConnectionError("socket detail SECRET-DIAGNOSTIC"),
    )
    sleeps = []

    with pytest.raises(ExternalServiceError) as exc_info:
        request_with_resilience(
            requests.Session(),
            "GET",
            "https://statsapi.mlb.com/api/v1/schedule",
            request_func=request_func,
            sleep=sleeps.append,
        )

    assert len(calls) == MAX_ATTEMPTS
    assert sleeps == list(BACKOFF_SECONDS)
    assert str(exc_info.value) == "MLB data temporarily unavailable. Please try again."
    assert "SECRET-DIAGNOSTIC" not in str(exc_info.value)
    assert "SECRET-DIAGNOSTIC" in exc_info.value.failure.detail


def test_429_is_retried_but_normal_4xx_fails_immediately():
    rate_limited, rate_calls = scripted(FakeResponse(429), FakeResponse(200, {"ok": True}))
    sleeps = []
    response = request_with_resilience(
        requests.Session(),
        "GET",
        "https://api.open-meteo.com/v1/forecast",
        request_func=rate_limited,
        sleep=sleeps.append,
    )
    assert response.status_code == 200
    assert len(rate_calls) == 2

    not_found, not_found_calls = scripted(FakeResponse(404))
    with pytest.raises(ExternalServiceError) as exc_info:
        request_with_resilience(
            requests.Session(),
            "GET",
            "https://statsapi.mlb.com/api/v1/missing",
            request_func=not_found,
            sleep=lambda _: None,
        )
    assert len(not_found_calls) == 1
    assert exc_info.value.failure.status_code == 404
    assert str(exc_info.value) == "MLB data temporarily unavailable. Please try again."


def test_invalid_json_fails_closed_without_retry_or_raw_decoder_message():
    request_func, calls = scripted(FakeResponse(200, json_error=ValueError("decoder internals")))
    with pytest.raises(ExternalServiceError) as exc_info:
        request_with_resilience(
            requests.Session(),
            "GET",
            "https://api.open-meteo.com/v1/forecast",
            request_func=request_func,
            sleep=lambda _: None,
        )

    assert len(calls) == 1
    assert str(exc_info.value) == "Weather data temporarily unavailable. Please try again."
    assert "decoder internals" not in str(exc_info.value)
    assert "decoder internals" in exc_info.value.failure.detail


def test_untracked_hosts_and_non_get_methods_are_exact_passthrough():
    third_party = FakeResponse(503, {"book": "unchanged"})
    request_func, calls = scripted(third_party)
    returned = request_with_resilience(
        requests.Session(),
        "GET",
        "https://example.com/api",
        request_func=request_func,
        sleep=lambda _: pytest.fail("untracked request must not sleep"),
    )
    assert returned is third_party
    assert len(calls) == 1

    post_response = FakeResponse(503, {"write": "unchanged"})
    post_func, post_calls = scripted(post_response)
    returned_post = request_with_resilience(
        requests.Session(),
        "POST",
        "https://statsapi.mlb.com/api/v1/something",
        request_func=post_func,
        sleep=lambda _: pytest.fail("non-GET request must not sleep"),
    )
    assert returned_post is post_response
    assert len(post_calls) == 1
