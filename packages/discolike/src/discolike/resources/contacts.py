from __future__ import annotations

import pydantic

from discolike._jobs import FAMILY_CONTACTMATCH
from discolike._jobs import FAMILY_DISCOGEN
from discolike._jobs import AsyncJob
from discolike._jobs import Job
from discolike._models import DiscolikeModel
from discolike.requests import BulkContactMatchRequest
from discolike.requests import ContactFilters
from discolike.requests import ContactGenerateRequest
from discolike.requests import ContactsCountParams
from discolike.requests import ContactsLookupParams
from discolike.requests import ContactsMatchParams
from discolike.requests import ContactsSearchParams
from discolike.resources._base import AsyncAPIResource
from discolike.resources._base import SyncAPIResource
from discolike.resources._base import api_route
from discolike.resources.companies import CompanyProfile
from discolike.resources.discovery import Count


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


class ContactsByCompany(CompanyProfile):
    contacts: list[Contact] = pydantic.Field(default_factory=list)
    email_pattern: str | None = None
    email_pattern_confidence: float | None = None
    email_pattern_guess: str | None = None


class ContactsDiscoverResponse(DiscolikeModel):
    results: dict[str, ContactsByCompany] = pydantic.Field(default_factory=dict)
    total_contacts: int | None = None
    total_domains: int | None = None


class ContactsResource(SyncAPIResource):
    @api_route("GET", "/contacts")
    def search(self, params: ContactsSearchParams) -> list[Contact]:
        response = self._transport.request("GET", "/contacts", params=params.to_wire())
        return [Contact.model_validate(item) for item in response.json()]

    @api_route("GET", "/contacts/count")
    def count(self, params: ContactsCountParams) -> Count:
        return Count.model_validate(self._transport.request("GET", "/contacts/count", params=params.to_wire()).json())

    @api_route("GET", "/contacts/lookup")
    def lookup(self, params: ContactsLookupParams) -> Contact:
        return Contact.model_validate(
            self._transport.request("GET", "/contacts/lookup", params=params.to_wire()).json()
        )

    @api_route("GET", "/contacts/match")
    def match(self, params: ContactsMatchParams) -> ContactMatchResponse:
        response = self._transport.request("GET", "/contacts/match", params=params.to_wire())
        return ContactMatchResponse.model_validate(response.json())

    @api_route("POST", "/contacts/bulk-match")
    def bulk_match(self, request: BulkContactMatchRequest) -> Job:
        response = self._transport.request("POST", "/contacts/bulk-match", json_body=request.to_wire())
        return Job(self._transport, task_family=FAMILY_CONTACTMATCH, task_id=response.json()["task_id"])

    @api_route("POST", "/contacts/discover")
    def discover(self, request: ContactFilters) -> ContactsDiscoverResponse:
        response = self._transport.request("POST", "/contacts/discover", json_body=request.to_wire())
        return ContactsDiscoverResponse.model_validate(response.json())

    @api_route("POST", "/contacts/discover/generate")
    def generate(self, request: ContactGenerateRequest) -> Job:
        response = self._transport.request("POST", "/contacts/discover/generate", json_body=request.to_wire())
        return Job(self._transport, task_family=FAMILY_DISCOGEN, task_id=response.json()["task_id"])


class AsyncContactsResource(AsyncAPIResource):
    @api_route("GET", "/contacts")
    async def search(self, params: ContactsSearchParams) -> list[Contact]:
        response = await self._transport.request("GET", "/contacts", params=params.to_wire())
        return [Contact.model_validate(item) for item in response.json()]

    @api_route("GET", "/contacts/count")
    async def count(self, params: ContactsCountParams) -> Count:
        response = await self._transport.request("GET", "/contacts/count", params=params.to_wire())
        return Count.model_validate(response.json())

    @api_route("GET", "/contacts/lookup")
    async def lookup(self, params: ContactsLookupParams) -> Contact:
        response = await self._transport.request("GET", "/contacts/lookup", params=params.to_wire())
        return Contact.model_validate(response.json())

    @api_route("GET", "/contacts/match")
    async def match(self, params: ContactsMatchParams) -> ContactMatchResponse:
        response = await self._transport.request("GET", "/contacts/match", params=params.to_wire())
        return ContactMatchResponse.model_validate(response.json())

    @api_route("POST", "/contacts/bulk-match")
    async def bulk_match(self, request: BulkContactMatchRequest) -> AsyncJob:
        response = await self._transport.request("POST", "/contacts/bulk-match", json_body=request.to_wire())
        return AsyncJob(self._transport, task_family=FAMILY_CONTACTMATCH, task_id=response.json()["task_id"])

    @api_route("POST", "/contacts/discover")
    async def discover(self, request: ContactFilters) -> ContactsDiscoverResponse:
        response = await self._transport.request("POST", "/contacts/discover", json_body=request.to_wire())
        return ContactsDiscoverResponse.model_validate(response.json())

    @api_route("POST", "/contacts/discover/generate")
    async def generate(self, request: ContactGenerateRequest) -> AsyncJob:
        response = await self._transport.request("POST", "/contacts/discover/generate", json_body=request.to_wire())
        return AsyncJob(self._transport, task_family=FAMILY_DISCOGEN, task_id=response.json()["task_id"])
