from __future__ import annotations

from typing import Any

import httpx

from discolike._config import DEFAULT_BASE_URL, resolve_api_key
from discolike._transport import AsyncTransport, Transport
from discolike.resources.account import AccountResource, AsyncAccountResource
from discolike.resources.companies import AsyncCompaniesResource, CompaniesResource
from discolike.resources.discovery import AsyncDiscoveryResource, Company, Count, DiscoveryResource

DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_RETRIES = 3


class Discolike:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._transport = Transport(
            resolve_api_key(api_key),
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            http_client=http_client,
        )
        self.account = AccountResource(self._transport)
        self.companies = CompaniesResource(self._transport)
        self._discovery = DiscoveryResource(self._transport)

    def discover(self, **kwargs: Any) -> list[Company]:
        return self._discovery.discover(**kwargs)

    def count(self, **kwargs: Any) -> Count:
        return self._discovery.count(**kwargs)

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> Discolike:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


class AsyncDiscolike:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._transport = AsyncTransport(
            resolve_api_key(api_key),
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            http_client=http_client,
        )
        self.account = AsyncAccountResource(self._transport)
        self.companies = AsyncCompaniesResource(self._transport)
        self._discovery = AsyncDiscoveryResource(self._transport)

    async def discover(self, **kwargs: Any) -> list[Company]:
        return await self._discovery.discover(**kwargs)

    async def count(self, **kwargs: Any) -> Count:
        return await self._discovery.count(**kwargs)

    async def aclose(self) -> None:
        await self._transport.aclose()

    async def __aenter__(self) -> AsyncDiscolike:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()
