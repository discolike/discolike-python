from __future__ import annotations

from typing import Any

import pydantic

from discolike._jobs import FAMILY_CONTACTMATCH
from discolike._jobs import FAMILY_DISCOGEN
from discolike._jobs import AsyncJob
from discolike._jobs import Job
from discolike._models import DiscolikeModel
from discolike._transport import drop_none
from discolike.resources._base import AsyncAPIResource
from discolike.resources._base import SyncAPIResource
from discolike.resources._base import api_route


class Contact(DiscolikeModel):
    persona_id: int | None = None
    domain: str | None = None
    name: str | None = None
    title: str | None = None
    email: str | None = None


class ContactMatchQuery(DiscolikeModel):
    name: str | None = None
    company_name: str | None = None
    domain: str | None = None
    person_country: str | None = None


class ContactMatchResult(DiscolikeModel):
    persona_id: int | None = None
    name: str | None = None
    title: str | None = None
    domain: str | None = None
    company_name: str | None = None
    match_score: float | None = None


class ContactMatchResponse(DiscolikeModel):
    query: ContactMatchQuery | None = None
    matches: list[ContactMatchResult] = pydantic.Field(default_factory=list)


class ContactsByCompany(DiscolikeModel):
    domain: str | None = None
    name: str | None = None
    contacts: list[Contact] = pydantic.Field(default_factory=list)
    email_pattern: str | None = None


class ContactsResource(SyncAPIResource):
    @api_route("GET", "/contacts")
    def search(
        self,
        *,
        icp_prompt: str | None = None,
        icp_text: str | None = None,
        seniority: list[str] | None = None,
        negate_seniority: list[str] | None = None,
        department: list[str] | None = None,
        negate_department: list[str] | None = None,
        skills: list[str] | None = None,
        name: str | None = None,
        title: list[str] | None = None,
        negate_title: list[str] | None = None,
        summary: str | None = None,
        negate_summary: str | None = None,
        person_country: list[str] | None = None,
        negate_person_country: list[str] | None = None,
        person_state: list[str] | None = None,
        has_email: bool | None = None,
        email_validated: bool | None = None,
        has_phone: bool | None = None,
        has_mobile: bool | None = None,
        has_linkedin: bool | None = None,
        min_connections: int | None = None,
        jobstart_date: str | None = None,
        persona_id: list[int] | None = None,
        domain: list[str] | None = None,
        filter_industry: list[str] | None = None,
        negate_filter_industry: list[str] | None = None,
        filter_country: list[str] | None = None,
        negate_filter_country: list[str] | None = None,
        filter_state: list[str] | None = None,
        negate_filter_state: list[str] | None = None,
        employee_range: str | None = None,
        inclusion_query_id: list[str] | None = None,
        exclusion_query_id: list[str] | None = None,
        max_records: int | None = None,
        max_companies: int | None = None,
        offset: int | None = None,
    ) -> list[Contact]:
        params = {k: v for k, v in locals().items() if k != "self"}
        response = self._transport.request("GET", "/contacts", params=params)
        return [Contact.model_validate(item) for item in response.json()]

    @api_route("GET", "/contacts/count")
    def count(
        self,
        *,
        icp_prompt: str | None = None,
        icp_text: str | None = None,
        seniority: list[str] | None = None,
        negate_seniority: list[str] | None = None,
        department: list[str] | None = None,
        negate_department: list[str] | None = None,
        skills: list[str] | None = None,
        name: str | None = None,
        title: list[str] | None = None,
        negate_title: list[str] | None = None,
        summary: str | None = None,
        negate_summary: str | None = None,
        person_country: list[str] | None = None,
        negate_person_country: list[str] | None = None,
        person_state: list[str] | None = None,
        has_email: bool | None = None,
        email_validated: bool | None = None,
        has_phone: bool | None = None,
        has_mobile: bool | None = None,
        has_linkedin: bool | None = None,
        min_connections: int | None = None,
        jobstart_date: str | None = None,
        persona_id: list[int] | None = None,
        domain: list[str] | None = None,
        filter_industry: list[str] | None = None,
        negate_filter_industry: list[str] | None = None,
        filter_country: list[str] | None = None,
        negate_filter_country: list[str] | None = None,
        filter_state: list[str] | None = None,
        negate_filter_state: list[str] | None = None,
        employee_range: str | None = None,
        inclusion_query_id: list[str] | None = None,
        exclusion_query_id: list[str] | None = None,
    ) -> DiscolikeModel:
        params = {k: v for k, v in locals().items() if k != "self"}
        return DiscolikeModel.model_validate(self._transport.request("GET", "/contacts/count", params=params).json())

    @api_route("GET", "/contacts/lookup")
    def lookup(
        self, *, persona_id: int | None = None, linkedin: str | None = None, email: str | None = None
    ) -> Contact:
        params = {k: v for k, v in locals().items() if k != "self"}
        return Contact.model_validate(self._transport.request("GET", "/contacts/lookup", params=params).json())

    @api_route("GET", "/contacts/match")
    def match(
        self,
        *,
        name: str,
        company_name: str | None = None,
        domain: str | None = None,
        person_country: str | None = None,
        limit: int | None = None,
    ) -> ContactMatchResponse:
        params = {k: v for k, v in locals().items() if k != "self"}
        return ContactMatchResponse.model_validate(
            self._transport.request("GET", "/contacts/match", params=params).json()
        )

    @api_route("POST", "/contacts/bulk-match")
    def bulk_match(
        self,
        *,
        queries: list[dict[str, Any]],
        enrich: bool | None = None,
        limit: int | None = None,
    ) -> Job:
        body = {k: v for k, v in locals().items() if k != "self"}
        response = self._transport.request("POST", "/contacts/bulk-match", json_body=drop_none(body))
        return Job(self._transport, task_family=FAMILY_CONTACTMATCH, task_id=response.json()["task_id"])

    # jobstart_date shipped in the platform repo but is not in the deployed spec yet
    @api_route("POST", "/contacts/discover", ignore_params=("jobstart_date",))
    def discover(
        self,
        *,
        icp_prompt: str | None = None,
        icp_text: str | None = None,
        seniority: list[str] | None = None,
        negate_seniority: list[str] | None = None,
        department: list[str] | None = None,
        negate_department: list[str] | None = None,
        skills: list[str] | None = None,
        name: str | None = None,
        title: list[str] | None = None,
        negate_title: list[str] | None = None,
        summary: str | None = None,
        negate_summary: str | None = None,
        person_country: list[str] | None = None,
        negate_person_country: list[str] | None = None,
        person_state: list[str] | None = None,
        has_email: bool | None = None,
        email_validated: bool | None = None,
        has_phone: bool | None = None,
        has_mobile: bool | None = None,
        has_linkedin: bool | None = None,
        min_connections: int | None = None,
        jobstart_date: str | None = None,
        persona_id: list[int] | None = None,
        domain: list[str] | None = None,
        filter_industry: list[str] | None = None,
        negate_filter_industry: list[str] | None = None,
        filter_country: list[str] | None = None,
        negate_filter_country: list[str] | None = None,
        filter_state: list[str] | None = None,
        negate_filter_state: list[str] | None = None,
        employee_range: str | None = None,
        inclusion_query_id: list[str] | None = None,
        exclusion_query_id: list[str] | None = None,
        max_records: int | None = None,
        max_companies: int | None = None,
        offset: int | None = None,
        results_by_company: int | None = None,
        include_search_contacts: bool | None = None,
        consensus: int | None = None,
    ) -> DiscolikeModel:
        body = {k: v for k, v in locals().items() if k != "self"}
        response = self._transport.request("POST", "/contacts/discover", json_body=drop_none(body))
        return DiscolikeModel.model_validate(response.json())

    @api_route("POST", "/contacts/discover/generate")
    def generate(
        self,
        *,
        icp_text: str,
        domains: list[str] | None = None,
        inclusion_query_id: list[str] | None = None,
        context_mode: str | None = None,
        integration_id: str | None = None,
        search_provider_id: str | None = None,
        search_context_size: str | None = None,
        max_contacts_per_domain: int | None = None,
        max_company_records: int | None = None,
    ) -> Job:
        body = {k: v for k, v in locals().items() if k != "self"}
        response = self._transport.request("POST", "/contacts/discover/generate", json_body=drop_none(body))
        return Job(self._transport, task_family=FAMILY_DISCOGEN, task_id=response.json()["task_id"])


class AsyncContactsResource(AsyncAPIResource):
    @api_route("GET", "/contacts")
    async def search(
        self,
        *,
        icp_prompt: str | None = None,
        icp_text: str | None = None,
        seniority: list[str] | None = None,
        negate_seniority: list[str] | None = None,
        department: list[str] | None = None,
        negate_department: list[str] | None = None,
        skills: list[str] | None = None,
        name: str | None = None,
        title: list[str] | None = None,
        negate_title: list[str] | None = None,
        summary: str | None = None,
        negate_summary: str | None = None,
        person_country: list[str] | None = None,
        negate_person_country: list[str] | None = None,
        person_state: list[str] | None = None,
        has_email: bool | None = None,
        email_validated: bool | None = None,
        has_phone: bool | None = None,
        has_mobile: bool | None = None,
        has_linkedin: bool | None = None,
        min_connections: int | None = None,
        jobstart_date: str | None = None,
        persona_id: list[int] | None = None,
        domain: list[str] | None = None,
        filter_industry: list[str] | None = None,
        negate_filter_industry: list[str] | None = None,
        filter_country: list[str] | None = None,
        negate_filter_country: list[str] | None = None,
        filter_state: list[str] | None = None,
        negate_filter_state: list[str] | None = None,
        employee_range: str | None = None,
        inclusion_query_id: list[str] | None = None,
        exclusion_query_id: list[str] | None = None,
        max_records: int | None = None,
        max_companies: int | None = None,
        offset: int | None = None,
    ) -> list[Contact]:
        params = {k: v for k, v in locals().items() if k != "self"}
        response = await self._transport.request("GET", "/contacts", params=params)
        return [Contact.model_validate(item) for item in response.json()]

    @api_route("GET", "/contacts/count")
    async def count(
        self,
        *,
        icp_prompt: str | None = None,
        icp_text: str | None = None,
        seniority: list[str] | None = None,
        negate_seniority: list[str] | None = None,
        department: list[str] | None = None,
        negate_department: list[str] | None = None,
        skills: list[str] | None = None,
        name: str | None = None,
        title: list[str] | None = None,
        negate_title: list[str] | None = None,
        summary: str | None = None,
        negate_summary: str | None = None,
        person_country: list[str] | None = None,
        negate_person_country: list[str] | None = None,
        person_state: list[str] | None = None,
        has_email: bool | None = None,
        email_validated: bool | None = None,
        has_phone: bool | None = None,
        has_mobile: bool | None = None,
        has_linkedin: bool | None = None,
        min_connections: int | None = None,
        jobstart_date: str | None = None,
        persona_id: list[int] | None = None,
        domain: list[str] | None = None,
        filter_industry: list[str] | None = None,
        negate_filter_industry: list[str] | None = None,
        filter_country: list[str] | None = None,
        negate_filter_country: list[str] | None = None,
        filter_state: list[str] | None = None,
        negate_filter_state: list[str] | None = None,
        employee_range: str | None = None,
        inclusion_query_id: list[str] | None = None,
        exclusion_query_id: list[str] | None = None,
    ) -> DiscolikeModel:
        params = {k: v for k, v in locals().items() if k != "self"}
        response = await self._transport.request("GET", "/contacts/count", params=params)
        return DiscolikeModel.model_validate(response.json())

    @api_route("GET", "/contacts/lookup")
    async def lookup(
        self, *, persona_id: int | None = None, linkedin: str | None = None, email: str | None = None
    ) -> Contact:
        params = {k: v for k, v in locals().items() if k != "self"}
        response = await self._transport.request("GET", "/contacts/lookup", params=params)
        return Contact.model_validate(response.json())

    @api_route("GET", "/contacts/match")
    async def match(
        self,
        *,
        name: str,
        company_name: str | None = None,
        domain: str | None = None,
        person_country: str | None = None,
        limit: int | None = None,
    ) -> ContactMatchResponse:
        params = {k: v for k, v in locals().items() if k != "self"}
        response = await self._transport.request("GET", "/contacts/match", params=params)
        return ContactMatchResponse.model_validate(response.json())

    @api_route("POST", "/contacts/bulk-match")
    async def bulk_match(
        self,
        *,
        queries: list[dict[str, Any]],
        enrich: bool | None = None,
        limit: int | None = None,
    ) -> AsyncJob:
        body = {k: v for k, v in locals().items() if k != "self"}
        response = await self._transport.request("POST", "/contacts/bulk-match", json_body=drop_none(body))
        return AsyncJob(self._transport, task_family=FAMILY_CONTACTMATCH, task_id=response.json()["task_id"])

    # jobstart_date shipped in the platform repo but is not in the deployed spec yet
    @api_route("POST", "/contacts/discover", ignore_params=("jobstart_date",))
    async def discover(
        self,
        *,
        icp_prompt: str | None = None,
        icp_text: str | None = None,
        seniority: list[str] | None = None,
        negate_seniority: list[str] | None = None,
        department: list[str] | None = None,
        negate_department: list[str] | None = None,
        skills: list[str] | None = None,
        name: str | None = None,
        title: list[str] | None = None,
        negate_title: list[str] | None = None,
        summary: str | None = None,
        negate_summary: str | None = None,
        person_country: list[str] | None = None,
        negate_person_country: list[str] | None = None,
        person_state: list[str] | None = None,
        has_email: bool | None = None,
        email_validated: bool | None = None,
        has_phone: bool | None = None,
        has_mobile: bool | None = None,
        has_linkedin: bool | None = None,
        min_connections: int | None = None,
        jobstart_date: str | None = None,
        persona_id: list[int] | None = None,
        domain: list[str] | None = None,
        filter_industry: list[str] | None = None,
        negate_filter_industry: list[str] | None = None,
        filter_country: list[str] | None = None,
        negate_filter_country: list[str] | None = None,
        filter_state: list[str] | None = None,
        negate_filter_state: list[str] | None = None,
        employee_range: str | None = None,
        inclusion_query_id: list[str] | None = None,
        exclusion_query_id: list[str] | None = None,
        max_records: int | None = None,
        max_companies: int | None = None,
        offset: int | None = None,
        results_by_company: int | None = None,
        include_search_contacts: bool | None = None,
        consensus: int | None = None,
    ) -> DiscolikeModel:
        body = {k: v for k, v in locals().items() if k != "self"}
        response = await self._transport.request("POST", "/contacts/discover", json_body=drop_none(body))
        return DiscolikeModel.model_validate(response.json())

    @api_route("POST", "/contacts/discover/generate")
    async def generate(
        self,
        *,
        icp_text: str,
        domains: list[str] | None = None,
        inclusion_query_id: list[str] | None = None,
        context_mode: str | None = None,
        integration_id: str | None = None,
        search_provider_id: str | None = None,
        search_context_size: str | None = None,
        max_contacts_per_domain: int | None = None,
        max_company_records: int | None = None,
    ) -> AsyncJob:
        body = {k: v for k, v in locals().items() if k != "self"}
        response = await self._transport.request("POST", "/contacts/discover/generate", json_body=drop_none(body))
        return AsyncJob(self._transport, task_family=FAMILY_DISCOGEN, task_id=response.json()["task_id"])
