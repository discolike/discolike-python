from __future__ import annotations

import httpx2

from discolike._auth import DiscolikeAuth
from discolike._config import DEFAULT_BASE_URL
from discolike._config import load_credential
from discolike._config import resolve_credential
from discolike._config import save_credential
from discolike._credentials import Credential
from discolike._jobs import AsyncJob
from discolike._jobs import Job
from discolike._transport import AsyncTransport
from discolike._transport import Transport
from discolike.requests import AppendParams
from discolike.requests import CountParams
from discolike.requests import DiscoverParams
from discolike.requests import SegmentFileParams
from discolike.requests import SegmentParams
from discolike.requests import ValidateIcpRequest
from discolike.resources._base import FileInput
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
from discolike.resources.email import AsyncEmailResource
from discolike.resources.email import EmailResource
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


def _build_auth(*, api_key: str | None, auth: Credential | None) -> DiscolikeAuth:
    # The config file is read back and written only when the credential came from it.
    credential = resolve_credential(api_key=api_key, auth=auth)
    if auth is not None:
        return DiscolikeAuth(credential)
    return DiscolikeAuth(credential, on_update=save_credential, reload=load_credential)


class Discolike:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        auth: Credential | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx2.Client | None = None,
    ) -> None:
        self._attach(
            Transport(
                _build_auth(api_key=api_key, auth=auth),
                base_url=base_url,
                timeout=timeout,
                max_retries=max_retries,
                http_client=http_client,
            )
        )

    def _attach(self, transport: Transport) -> None:
        self._transport = transport
        self.account = AccountResource(self._transport)
        self.companies = CompaniesResource(self._transport)
        self.contacts = ContactsResource(self._transport)
        self.match = MatchResource(self._transport)
        self.discogen = DiscogenResource(self._transport)
        self.email = EmailResource(self._transport)
        self.queries = QueriesResource(self._transport)
        self.search_providers = SearchProvidersResource(self._transport)
        self.llm_providers = LLMProvidersResource(self._transport)
        self._discovery = DiscoveryResource(self._transport)
        self._validate = ValidateResource(self._transport)
        self._enrich = EnrichResource(self._transport)

    def with_options(self, *, timeout: float | httpx2.Timeout) -> Discolike:
        """A client view with a different request timeout, sharing this client's connection pool."""
        clone = object.__new__(Discolike)
        clone._attach(self._transport.with_timeout(timeout))
        return clone

    def discover(self, params: DiscoverParams) -> list[Company]:
        return self._discovery.discover(params)

    def count(self, params: CountParams) -> Count:
        return self._discovery.count(params)

    def validate_icp(self, request: ValidateIcpRequest) -> Job:
        return self._validate.icp(request)

    def append(self, params: AppendParams, *, file: FileInput | None = None) -> list[AppendResult] | bytes:
        return self._enrich.append(params, file=file)

    def segment(self, params: SegmentParams) -> Job:
        return self._enrich.segment(params)

    def segment_file(self, params: SegmentFileParams, *, file: FileInput) -> Job:
        return self._enrich.segment_file(params, file=file)

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
        auth: Credential | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._attach(
            AsyncTransport(
                _build_auth(api_key=api_key, auth=auth),
                base_url=base_url,
                timeout=timeout,
                max_retries=max_retries,
                http_client=http_client,
            )
        )

    def _attach(self, transport: AsyncTransport) -> None:
        self._transport = transport
        self.account = AsyncAccountResource(self._transport)
        self.companies = AsyncCompaniesResource(self._transport)
        self.contacts = AsyncContactsResource(self._transport)
        self.match = AsyncMatchResource(self._transport)
        self.discogen = AsyncDiscogenResource(self._transport)
        self.email = AsyncEmailResource(self._transport)
        self.queries = AsyncQueriesResource(self._transport)
        self.search_providers = AsyncSearchProvidersResource(self._transport)
        self.llm_providers = AsyncLLMProvidersResource(self._transport)
        self._discovery = AsyncDiscoveryResource(self._transport)
        self._validate = AsyncValidateResource(self._transport)
        self._enrich = AsyncEnrichResource(self._transport)

    def with_options(self, *, timeout: float | httpx2.Timeout) -> AsyncDiscolike:
        """A client view with a different request timeout, sharing this client's connection pool."""
        clone = object.__new__(AsyncDiscolike)
        clone._attach(self._transport.with_timeout(timeout))
        return clone

    async def discover(self, params: DiscoverParams) -> list[Company]:
        return await self._discovery.discover(params)

    async def count(self, params: CountParams) -> Count:
        return await self._discovery.count(params)

    async def validate_icp(self, request: ValidateIcpRequest) -> AsyncJob:
        return await self._validate.icp(request)

    async def append(self, params: AppendParams, *, file: FileInput | None = None) -> list[AppendResult] | bytes:
        return await self._enrich.append(params, file=file)

    async def segment(self, params: SegmentParams) -> AsyncJob:
        return await self._enrich.segment(params)

    async def segment_file(self, params: SegmentFileParams, *, file: FileInput) -> AsyncJob:
        return await self._enrich.segment_file(params, file=file)

    async def aclose(self) -> None:
        await self._transport.aclose()

    async def __aenter__(self) -> AsyncDiscolike:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()
