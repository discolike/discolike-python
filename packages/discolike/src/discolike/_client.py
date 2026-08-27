from __future__ import annotations

import pathlib
from typing import BinaryIO

import httpx2

from discolike._config import DEFAULT_BASE_URL
from discolike._config import resolve_api_key
from discolike._jobs import AsyncJob
from discolike._jobs import Job
from discolike._transport import AsyncTransport
from discolike._transport import Transport
from discolike.requests import ValidateIcpRequest
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


class Discolike:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx2.Client | None = None,
    ) -> None:
        self._attach(
            Transport(
                resolve_api_key(api_key),
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

    def discover(
        self,
        *,
        domain: list[str] | None = None,
        exclude_domain: list[str] | None = None,
        icp_text: str | None = None,
        icp_prompt: str | None = None,
        phrase_match: list[str] | None = None,
        negate_phrase_match: list[str] | None = None,
        subdomain: list[str] | None = None,
        negate_subdomain: list[str] | None = None,
        tech_stack: list[str] | None = None,
        negate_tech_stack: list[str] | None = None,
        category: list[str] | None = None,
        negate_category: list[str] | None = None,
        state: list[str] | None = None,
        negate_state: list[str] | None = None,
        country: list[str] | None = None,
        negate_country: list[str] | None = None,
        social: list[str] | None = None,
        negate_social: list[str] | None = None,
        language: list[str] | None = None,
        negate_language: list[str] | None = None,
        business_model: list[str] | None = None,
        negate_business_model: list[str] | None = None,
        employee_range: str | None = None,
        revenue_range: str | None = None,
        start_date: str | None = None,
        redirect: bool | None = None,
        exclude_leadgen: bool | None = None,
        min_digital_footprint: int | None = None,
        max_digital_footprint: int | None = None,
        min_similarity: int | None = None,
        consensus: int | None = None,
        variance: str | None = None,
        retrieval: bool | None = None,
        enhanced: bool | None = None,
        include_search_domains: bool | None = None,
        auto_icp_text: bool | None = None,
        auto_phrase_match: bool | None = None,
        max_records: int | None = None,
        offset: int | None = None,
        exclusion_query_id: list[str] | None = None,
        inclusion_query_id: list[str] | None = None,
    ) -> list[Company]:
        return self._discovery.discover(
            domain=domain,
            exclude_domain=exclude_domain,
            icp_text=icp_text,
            icp_prompt=icp_prompt,
            phrase_match=phrase_match,
            negate_phrase_match=negate_phrase_match,
            subdomain=subdomain,
            negate_subdomain=negate_subdomain,
            tech_stack=tech_stack,
            negate_tech_stack=negate_tech_stack,
            category=category,
            negate_category=negate_category,
            state=state,
            negate_state=negate_state,
            country=country,
            negate_country=negate_country,
            social=social,
            negate_social=negate_social,
            language=language,
            negate_language=negate_language,
            business_model=business_model,
            negate_business_model=negate_business_model,
            employee_range=employee_range,
            revenue_range=revenue_range,
            start_date=start_date,
            redirect=redirect,
            exclude_leadgen=exclude_leadgen,
            min_digital_footprint=min_digital_footprint,
            max_digital_footprint=max_digital_footprint,
            min_similarity=min_similarity,
            consensus=consensus,
            variance=variance,
            retrieval=retrieval,
            enhanced=enhanced,
            include_search_domains=include_search_domains,
            auto_icp_text=auto_icp_text,
            auto_phrase_match=auto_phrase_match,
            max_records=max_records,
            offset=offset,
            exclusion_query_id=exclusion_query_id,
            inclusion_query_id=inclusion_query_id,
        )

    def count(
        self,
        *,
        phrase_match: list[str] | None = None,
        negate_phrase_match: list[str] | None = None,
        subdomain: list[str] | None = None,
        negate_subdomain: list[str] | None = None,
        tech_stack: list[str] | None = None,
        negate_tech_stack: list[str] | None = None,
        category: list[str] | None = None,
        negate_category: list[str] | None = None,
        min_digital_footprint: int | None = None,
        max_digital_footprint: int | None = None,
        state: list[str] | None = None,
        negate_state: list[str] | None = None,
        country: list[str] | None = None,
        negate_country: list[str] | None = None,
        start_date: str | None = None,
        redirect: bool | None = None,
        social: list[str] | None = None,
        negate_social: list[str] | None = None,
        language: list[str] | None = None,
        negate_language: list[str] | None = None,
        employee_range: str | None = None,
        revenue_range: str | None = None,
        business_model: list[str] | None = None,
        negate_business_model: list[str] | None = None,
        exclude_leadgen: bool | None = None,
    ) -> Count:
        return self._discovery.count(
            phrase_match=phrase_match,
            negate_phrase_match=negate_phrase_match,
            subdomain=subdomain,
            negate_subdomain=negate_subdomain,
            tech_stack=tech_stack,
            negate_tech_stack=negate_tech_stack,
            category=category,
            negate_category=negate_category,
            min_digital_footprint=min_digital_footprint,
            max_digital_footprint=max_digital_footprint,
            state=state,
            negate_state=negate_state,
            country=country,
            negate_country=negate_country,
            start_date=start_date,
            redirect=redirect,
            social=social,
            negate_social=negate_social,
            language=language,
            negate_language=negate_language,
            employee_range=employee_range,
            revenue_range=revenue_range,
            business_model=business_model,
            negate_business_model=negate_business_model,
            exclude_leadgen=exclude_leadgen,
        )

    def validate_icp(self, request: ValidateIcpRequest) -> Job:
        return self._validate.icp(request)

    def append(
        self,
        *,
        file: pathlib.Path | str | BinaryIO | None = None,
        dataset: list[str] | None = None,
        domain_column: str | None = None,
        csv: bool | None = None,
        query_id: list[str] | None = None,
    ) -> list[AppendResult] | bytes:
        return self._enrich.append(
            file=file,
            dataset=dataset,
            domain_column=domain_column,
            csv=csv,
            query_id=query_id,
        )

    def segment(
        self,
        *,
        domains: list[str] | None = None,
        file: pathlib.Path | str | BinaryIO | None = None,
        domain_column: str | None = None,
        max_segments: int | None = None,
        query_id: list[str] | None = None,
    ) -> Job:
        return self._enrich.segment(
            domains=domains,
            file=file,
            domain_column=domain_column,
            max_segments=max_segments,
            query_id=query_id,
        )

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
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._attach(
            AsyncTransport(
                resolve_api_key(api_key),
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

    async def discover(
        self,
        *,
        domain: list[str] | None = None,
        exclude_domain: list[str] | None = None,
        icp_text: str | None = None,
        icp_prompt: str | None = None,
        phrase_match: list[str] | None = None,
        negate_phrase_match: list[str] | None = None,
        subdomain: list[str] | None = None,
        negate_subdomain: list[str] | None = None,
        tech_stack: list[str] | None = None,
        negate_tech_stack: list[str] | None = None,
        category: list[str] | None = None,
        negate_category: list[str] | None = None,
        state: list[str] | None = None,
        negate_state: list[str] | None = None,
        country: list[str] | None = None,
        negate_country: list[str] | None = None,
        social: list[str] | None = None,
        negate_social: list[str] | None = None,
        language: list[str] | None = None,
        negate_language: list[str] | None = None,
        business_model: list[str] | None = None,
        negate_business_model: list[str] | None = None,
        employee_range: str | None = None,
        revenue_range: str | None = None,
        start_date: str | None = None,
        redirect: bool | None = None,
        exclude_leadgen: bool | None = None,
        min_digital_footprint: int | None = None,
        max_digital_footprint: int | None = None,
        min_similarity: int | None = None,
        consensus: int | None = None,
        variance: str | None = None,
        retrieval: bool | None = None,
        enhanced: bool | None = None,
        include_search_domains: bool | None = None,
        auto_icp_text: bool | None = None,
        auto_phrase_match: bool | None = None,
        max_records: int | None = None,
        offset: int | None = None,
        exclusion_query_id: list[str] | None = None,
        inclusion_query_id: list[str] | None = None,
    ) -> list[Company]:
        return await self._discovery.discover(
            domain=domain,
            exclude_domain=exclude_domain,
            icp_text=icp_text,
            icp_prompt=icp_prompt,
            phrase_match=phrase_match,
            negate_phrase_match=negate_phrase_match,
            subdomain=subdomain,
            negate_subdomain=negate_subdomain,
            tech_stack=tech_stack,
            negate_tech_stack=negate_tech_stack,
            category=category,
            negate_category=negate_category,
            state=state,
            negate_state=negate_state,
            country=country,
            negate_country=negate_country,
            social=social,
            negate_social=negate_social,
            language=language,
            negate_language=negate_language,
            business_model=business_model,
            negate_business_model=negate_business_model,
            employee_range=employee_range,
            revenue_range=revenue_range,
            start_date=start_date,
            redirect=redirect,
            exclude_leadgen=exclude_leadgen,
            min_digital_footprint=min_digital_footprint,
            max_digital_footprint=max_digital_footprint,
            min_similarity=min_similarity,
            consensus=consensus,
            variance=variance,
            retrieval=retrieval,
            enhanced=enhanced,
            include_search_domains=include_search_domains,
            auto_icp_text=auto_icp_text,
            auto_phrase_match=auto_phrase_match,
            max_records=max_records,
            offset=offset,
            exclusion_query_id=exclusion_query_id,
            inclusion_query_id=inclusion_query_id,
        )

    async def count(
        self,
        *,
        phrase_match: list[str] | None = None,
        negate_phrase_match: list[str] | None = None,
        subdomain: list[str] | None = None,
        negate_subdomain: list[str] | None = None,
        tech_stack: list[str] | None = None,
        negate_tech_stack: list[str] | None = None,
        category: list[str] | None = None,
        negate_category: list[str] | None = None,
        min_digital_footprint: int | None = None,
        max_digital_footprint: int | None = None,
        state: list[str] | None = None,
        negate_state: list[str] | None = None,
        country: list[str] | None = None,
        negate_country: list[str] | None = None,
        start_date: str | None = None,
        redirect: bool | None = None,
        social: list[str] | None = None,
        negate_social: list[str] | None = None,
        language: list[str] | None = None,
        negate_language: list[str] | None = None,
        employee_range: str | None = None,
        revenue_range: str | None = None,
        business_model: list[str] | None = None,
        negate_business_model: list[str] | None = None,
        exclude_leadgen: bool | None = None,
    ) -> Count:
        return await self._discovery.count(
            phrase_match=phrase_match,
            negate_phrase_match=negate_phrase_match,
            subdomain=subdomain,
            negate_subdomain=negate_subdomain,
            tech_stack=tech_stack,
            negate_tech_stack=negate_tech_stack,
            category=category,
            negate_category=negate_category,
            min_digital_footprint=min_digital_footprint,
            max_digital_footprint=max_digital_footprint,
            state=state,
            negate_state=negate_state,
            country=country,
            negate_country=negate_country,
            start_date=start_date,
            redirect=redirect,
            social=social,
            negate_social=negate_social,
            language=language,
            negate_language=negate_language,
            employee_range=employee_range,
            revenue_range=revenue_range,
            business_model=business_model,
            negate_business_model=negate_business_model,
            exclude_leadgen=exclude_leadgen,
        )

    async def validate_icp(self, request: ValidateIcpRequest) -> AsyncJob:
        return await self._validate.icp(request)

    async def append(
        self,
        *,
        file: pathlib.Path | str | BinaryIO | None = None,
        dataset: list[str] | None = None,
        domain_column: str | None = None,
        csv: bool | None = None,
        query_id: list[str] | None = None,
    ) -> list[AppendResult] | bytes:
        return await self._enrich.append(
            file=file,
            dataset=dataset,
            domain_column=domain_column,
            csv=csv,
            query_id=query_id,
        )

    async def segment(
        self,
        *,
        domains: list[str] | None = None,
        file: pathlib.Path | str | BinaryIO | None = None,
        domain_column: str | None = None,
        max_segments: int | None = None,
        query_id: list[str] | None = None,
    ) -> AsyncJob:
        return await self._enrich.segment(
            domains=domains,
            file=file,
            domain_column=domain_column,
            max_segments=max_segments,
            query_id=query_id,
        )

    async def aclose(self) -> None:
        await self._transport.aclose()

    async def __aenter__(self) -> AsyncDiscolike:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()
