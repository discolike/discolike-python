from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from typing import Any

import httpx2

from discolike._exceptions import APIConnectionError
from discolike._exceptions import raise_for_status
from discolike._version import __version__

IDEMPOTENT_METHODS = frozenset({"GET", "DELETE"})
RETRYABLE_STATUSES = frozenset({429, 502, 503, 504})
NON_IDEMPOTENT_RETRYABLE_STATUSES = frozenset({429})
NON_IDEMPOTENT_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (httpx2.ConnectError,)
BACKOFF_BASE_SECONDS = 0.5


def drop_none(params: Mapping[str, Any] | None) -> dict[str, Any]:
    return {key: value for key, value in (params or {}).items() if value is not None}


def _default_headers() -> dict[str, str]:
    return {"User-Agent": f"discolike-python/{__version__}"}


def _retryable_statuses(method: str) -> frozenset[int]:
    return RETRYABLE_STATUSES if method in IDEMPOTENT_METHODS else NON_IDEMPOTENT_RETRYABLE_STATUSES


def _retryable_exceptions(method: str) -> tuple[type[Exception], ...]:
    return (httpx2.TransportError,) if method in IDEMPOTENT_METHODS else NON_IDEMPOTENT_RETRYABLE_EXCEPTIONS


def _retry_delay(response: httpx2.Response | None, attempt: int) -> float:
    if response is not None:
        header = response.headers.get("Retry-After")
        if header and header.replace(".", "", 1).isdigit():
            return float(header)
    return BACKOFF_BASE_SECONDS * (2**attempt)


class Transport:
    def __init__(
        self,
        auth: httpx2.Auth,
        *,
        base_url: str,
        timeout: float,
        max_retries: int,
        http_client: httpx2.Client | None = None,
    ) -> None:
        if http_client is not None and not str(http_client.base_url):
            http_client.base_url = base_url
        self._client = http_client or httpx2.Client(base_url=base_url, timeout=timeout)
        self._client.auth = auth
        self._client.headers.update(_default_headers())
        self._max_retries = max_retries
        self._timeout_override: float | httpx2.Timeout | None = None
        self._is_view = False

    def with_timeout(self, timeout: float | httpx2.Timeout) -> Transport:
        clone = object.__new__(Transport)
        clone._client = self._client
        clone._max_retries = self._max_retries
        clone._timeout_override = timeout
        clone._is_view = True
        return clone

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,  # noqa: ANN401 -- forwarded verbatim to httpx2.Client.request
        files: Any = None,  # noqa: ANN401 -- forwarded verbatim to httpx2.Client.request
        data: Any = None,  # noqa: ANN401 -- forwarded verbatim to httpx2.Client.request
    ) -> httpx2.Response:
        clean_params = drop_none(params)
        timeout = self._timeout_override if self._timeout_override is not None else httpx2.USE_CLIENT_DEFAULT
        retryable_statuses = _retryable_statuses(method)
        retryable_exceptions = _retryable_exceptions(method)
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.request(
                    method, path, params=clean_params, json=json_body, files=files, data=data, timeout=timeout
                )
            except retryable_exceptions as exc:
                if attempt == self._max_retries:
                    raise APIConnectionError(f"Connection to DiscoLike API failed: {exc}") from exc
                time.sleep(_retry_delay(None, attempt))
                continue
            except httpx2.TransportError as exc:
                raise APIConnectionError(f"Connection to DiscoLike API failed: {exc}") from exc
            if response.status_code in retryable_statuses and attempt < self._max_retries:
                time.sleep(_retry_delay(response, attempt))
                continue
            raise_for_status(response)
            return response
        raise AssertionError("unreachable")

    def close(self) -> None:
        if not self._is_view:
            self._client.close()


class AsyncTransport:
    def __init__(
        self,
        auth: httpx2.Auth,
        *,
        base_url: str,
        timeout: float,
        max_retries: int,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        if http_client is not None and not str(http_client.base_url):
            http_client.base_url = base_url
        self._client = http_client or httpx2.AsyncClient(base_url=base_url, timeout=timeout)
        self._client.auth = auth
        self._client.headers.update(_default_headers())
        self._max_retries = max_retries
        self._timeout_override: float | httpx2.Timeout | None = None
        self._is_view = False

    def with_timeout(self, timeout: float | httpx2.Timeout) -> AsyncTransport:
        clone = object.__new__(AsyncTransport)
        clone._client = self._client
        clone._max_retries = self._max_retries
        clone._timeout_override = timeout
        clone._is_view = True
        return clone

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,  # noqa: ANN401 -- forwarded verbatim to httpx2.Client.request
        files: Any = None,  # noqa: ANN401 -- forwarded verbatim to httpx2.Client.request
        data: Any = None,  # noqa: ANN401 -- forwarded verbatim to httpx2.Client.request
    ) -> httpx2.Response:
        clean_params = drop_none(params)
        timeout = self._timeout_override if self._timeout_override is not None else httpx2.USE_CLIENT_DEFAULT
        retryable_statuses = _retryable_statuses(method)
        retryable_exceptions = _retryable_exceptions(method)
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.request(
                    method, path, params=clean_params, json=json_body, files=files, data=data, timeout=timeout
                )
            except retryable_exceptions as exc:
                if attempt == self._max_retries:
                    raise APIConnectionError(f"Connection to DiscoLike API failed: {exc}") from exc
                await asyncio.sleep(_retry_delay(None, attempt))
                continue
            except httpx2.TransportError as exc:
                raise APIConnectionError(f"Connection to DiscoLike API failed: {exc}") from exc
            if response.status_code in retryable_statuses and attempt < self._max_retries:
                await asyncio.sleep(_retry_delay(response, attempt))
                continue
            raise_for_status(response)
            return response
        raise AssertionError("unreachable")

    async def aclose(self) -> None:
        if not self._is_view:
            await self._client.aclose()
