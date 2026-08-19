from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

LOGGER = logging.getLogger("strikeoutking.http")

TRACKED_SERVICES = {
    "statsapi.mlb.com": "MLB data",
    "api.open-meteo.com": "Weather data",
}
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (0.20, 0.40)


@dataclass(frozen=True)
class ServiceFailure:
    service: str
    host: str
    method: str
    status_code: int | None
    detail: str


class ExternalServiceError(RuntimeError):
    """Safe public exception with diagnostic detail retained for server logs."""

    def __init__(self, failure: ServiceFailure):
        self.failure = failure
        super().__init__(f"{failure.service} temporarily unavailable. Please try again.")


def _tracked_service(method: str, url: str) -> tuple[str, str] | None:
    if str(method).upper() != "GET":
        return None
    host = (urlparse(str(url)).hostname or "").lower()
    service = TRACKED_SERVICES.get(host)
    return (host, service) if service else None


def _raise_safe_failure(
    *,
    service: str,
    host: str,
    method: str,
    status_code: int | None,
    detail: str,
    cause: BaseException | None = None,
) -> None:
    failure = ServiceFailure(
        service=service,
        host=host,
        method=str(method).upper(),
        status_code=status_code,
        detail=detail,
    )
    LOGGER.warning(
        "%s request failed host=%s method=%s status=%s detail=%s",
        service,
        host,
        failure.method,
        status_code,
        detail,
        exc_info=cause is not None,
    )
    error = ExternalServiceError(failure)
    if cause is None:
        raise error
    raise error from cause


def request_with_resilience(
    session: requests.Session,
    method: str,
    url: str,
    *,
    request_func: Callable[..., requests.Response],
    sleep: Callable[[float], None] = time.sleep,
    **kwargs,
) -> requests.Response:
    """Retry only transient GET failures for MLB/Open-Meteo and fail closed.

    All other hosts and all non-GET methods pass through unchanged. Successful
    responses are returned as-is; no cached/stale/fabricated payload is ever
    substituted.
    """
    tracked = _tracked_service(method, url)
    if tracked is None:
        return request_func(session, method, url, **kwargs)

    host, service = tracked
    last_exception: BaseException | None = None

    for attempt in range(MAX_ATTEMPTS):
        try:
            response = request_func(session, method, url, **kwargs)
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exception = exc
            if attempt < MAX_ATTEMPTS - 1:
                sleep(BACKOFF_SECONDS[attempt])
                continue
            _raise_safe_failure(
                service=service,
                host=host,
                method=method,
                status_code=None,
                detail=f"{type(exc).__name__}: {exc}",
                cause=exc,
            )
        except requests.RequestException as exc:
            _raise_safe_failure(
                service=service,
                host=host,
                method=method,
                status_code=None,
                detail=f"{type(exc).__name__}: {exc}",
                cause=exc,
            )

        status = int(getattr(response, "status_code", 0) or 0)
        if status in RETRYABLE_STATUS_CODES and attempt < MAX_ATTEMPTS - 1:
            sleep(BACKOFF_SECONDS[attempt])
            continue
        if status >= 400:
            _raise_safe_failure(
                service=service,
                host=host,
                method=method,
                status_code=status,
                detail=f"HTTP {status}",
            )

        # Validate a successful tracked response before callers can expose a
        # decoder traceback in Streamlit. The payload is not transformed.
        try:
            response.json()
        except ValueError as exc:
            _raise_safe_failure(
                service=service,
                host=host,
                method=method,
                status_code=status or None,
                detail=f"Invalid JSON: {exc}",
                cause=exc,
            )
        return response

    # Defensive only; all loop exits above either return or raise.
    _raise_safe_failure(
        service=service,
        host=host,
        method=method,
        status_code=None,
        detail=f"request exhausted retries: {last_exception}",
        cause=last_exception,
    )


_ORIGINAL_SESSION_REQUEST = requests.Session.request
_INSTALLED = False


def _resilient_session_request(self: requests.Session, method: str, url: str, **kwargs):
    return request_with_resilience(
        self,
        method,
        url,
        request_func=_ORIGINAL_SESSION_REQUEST,
        **kwargs,
    )


def install_requests_resilience() -> None:
    """Install the host-scoped requests guard once for this Python process."""
    global _INSTALLED
    if _INSTALLED:
        return
    requests.Session.request = _resilient_session_request
    _INSTALLED = True
