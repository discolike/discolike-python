from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from typing import Any

import httpx

from discolike._exceptions import APIConnectionError, raise_for_status
from discolike._version import __version__

RETRYABLE_STATUSES = frozenset({429, 502, 503, 504})
BACKOFF_BASE_SECONDS = 0.5


def drop_none(params: Mapping[str, Any] | None) -> dict[str, Any]:
    return {key: value for key, value in (params or {}).items() if value is not None}


def _default_headers(api_key: str) -> dict[str, str]:
    return {"X-discolike-key": api_key, "User-Agent": f"discolike-python/{__version__}"}


def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
    if response is not None:
        header = response.headers.get("Retry-After")
        if header and header.replace(".", "", 1).isdigit():
            return float(header)
    return BACKOFF_BASE_SECONDS * (2**attempt)


class Transport:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        timeout: float,
        max_retries: int,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._client = http_client or httpx.Client(base_url=base_url, timeout=timeout)
        self._client.headers.update(_default_headers(api_key))
        self._max_retries = max_retries

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        files: Any = None,
        data: Any = None,
    ) -> httpx.Response:
        clean_params = drop_none(params)
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.request(
                    method, path, params=clean_params, json=json_body, files=files, data=data
                )
            except httpx.TransportError as exc:
                if attempt == self._max_retries:
                    raise APIConnectionError(f"Connection to DiscoLike API failed: {exc}") from exc
                time.sleep(_retry_delay(None, attempt))
                continue
            if response.status_code in RETRYABLE_STATUSES and attempt < self._max_retries:
                time.sleep(_retry_delay(response, attempt))
                continue
            raise_for_status(response)
            return response
        raise AssertionError("unreachable")

    def close(self) -> None:
        self._client.close()


class AsyncTransport:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        timeout: float,
        max_retries: int,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = http_client or httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._client.headers.update(_default_headers(api_key))
        self._max_retries = max_retries

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        files: Any = None,
        data: Any = None,
    ) -> httpx.Response:
        clean_params = drop_none(params)
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.request(
                    method, path, params=clean_params, json=json_body, files=files, data=data
                )
            except httpx.TransportError as exc:
                if attempt == self._max_retries:
                    raise APIConnectionError(f"Connection to DiscoLike API failed: {exc}") from exc
                await asyncio.sleep(_retry_delay(None, attempt))
                continue
            if response.status_code in RETRYABLE_STATUSES and attempt < self._max_retries:
                await asyncio.sleep(_retry_delay(response, attempt))
                continue
            raise_for_status(response)
            return response
        raise AssertionError("unreachable")

    async def aclose(self) -> None:
        await self._client.aclose()
