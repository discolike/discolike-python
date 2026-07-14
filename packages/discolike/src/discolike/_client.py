from __future__ import annotations

from typing import Any

import httpx

from discolike._config import DEFAULT_BASE_URL
from discolike._config import resolve_api_key
from discolike._jobs import AsyncJob
from discolike._jobs import Job
from discolike._transport import AsyncTransport
from discolike._transport import Transport
from discolike.resources.account import AccountResource
from discolike.resources.account import AsyncAccountResource
from discolike.resources.companies import AsyncCompaniesResource
from discolike.resources.companies import CompaniesResource
from discolike.resources.contacts import AsyncContactsResource
from discolike.resources.contacts import ContactsResource
from discolike.resources.discogen import AsyncDiscogenResource
from discolike.resources.discogen import AsyncValidateResource
from discolike.resources.discogen import DiscogenResource
from discolike.resources.discogen import ValidateResource
from discolike.resources.discovery import AsyncDiscoveryResource
from discolike.resources.discovery import Company
from discolike.resources.discovery import Count
from discolike.resources.discovery import DiscoveryResource
from discolike.resources.enrich import AppendResult
from discolike.resources.enrich import AsyncEnrichResource
from discolike.resources.enrich import EnrichResource
from discolike.resources.match import AsyncMatchResource
from discolike.resources.match import MatchResource
from discolike.resources.providers import AsyncLLMProvidersResource
from discolike.resources.providers import AsyncSearchProvidersResource
from discolike.resources.providers import LLMProvidersResource
from discolike.resources.providers import SearchProvidersResource
from discolike.resources.queries import AsyncQueriesResource
from discolike.resources.queries import QueriesResource

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
        self.contacts = ContactsResource(self._transport)
        self.match = MatchResource(self._transport)
        self.discogen = DiscogenResource(self._transport)
        self.queries = QueriesResource(self._transport)
        self.search_providers = SearchProvidersResource(self._transport)
        self.llm_providers = LLMProvidersResource(self._transport)
        self._discovery = DiscoveryResource(self._transport)
        self._validate = ValidateResource(self._transport)
        self._enrich = EnrichResource(self._transport)

    def discover(self, **kwargs: Any) -> list[Company]:  # noqa: ANN401 -- forwards to DiscoveryResource.discover's typed signature
        return self._discovery.discover(**kwargs)

    def count(self, **kwargs: Any) -> Count:  # noqa: ANN401 -- forwards to DiscoveryResource.count's typed signature
        return self._discovery.count(**kwargs)

    def validate_icp(self, **kwargs: Any) -> Job:  # noqa: ANN401 -- forwards to ValidateResource.icp's typed signature
        return self._validate.icp(**kwargs)

    def append(self, **kwargs: Any) -> list[AppendResult] | bytes:  # noqa: ANN401 -- forwards to EnrichResource.append's typed signature
        return self._enrich.append(**kwargs)

    def segment(self, **kwargs: Any) -> Job:  # noqa: ANN401 -- forwards to EnrichResource.segment's typed signature
        return self._enrich.segment(**kwargs)

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
        self.contacts = AsyncContactsResource(self._transport)
        self.match = AsyncMatchResource(self._transport)
        self.discogen = AsyncDiscogenResource(self._transport)
        self.queries = AsyncQueriesResource(self._transport)
        self.search_providers = AsyncSearchProvidersResource(self._transport)
        self.llm_providers = AsyncLLMProvidersResource(self._transport)
        self._discovery = AsyncDiscoveryResource(self._transport)
        self._validate = AsyncValidateResource(self._transport)
        self._enrich = AsyncEnrichResource(self._transport)

    async def discover(self, **kwargs: Any) -> list[Company]:  # noqa: ANN401 -- forwards to AsyncDiscoveryResource.discover's typed signature
        return await self._discovery.discover(**kwargs)

    async def count(self, **kwargs: Any) -> Count:  # noqa: ANN401 -- forwards to AsyncDiscoveryResource.count's typed signature
        return await self._discovery.count(**kwargs)

    async def validate_icp(self, **kwargs: Any) -> AsyncJob:  # noqa: ANN401 -- forwards to AsyncValidateResource.icp's typed signature
        return await self._validate.icp(**kwargs)

    async def append(self, **kwargs: Any) -> list[AppendResult] | bytes:  # noqa: ANN401 -- forwards to AsyncEnrichResource.append's typed signature
        return await self._enrich.append(**kwargs)

    async def segment(self, **kwargs: Any) -> AsyncJob:  # noqa: ANN401 -- forwards to AsyncEnrichResource.segment's typed signature
        return await self._enrich.segment(**kwargs)

    async def aclose(self) -> None:
        await self._transport.aclose()

    async def __aenter__(self) -> AsyncDiscolike:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()
