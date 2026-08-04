from __future__ import annotations

import pydantic

from discolike._models import DiscolikeModel
from discolike.resources._base import AsyncAPIResource
from discolike.resources._base import SyncAPIResource
from discolike.resources._base import api_route


class CompanyStatus(DiscolikeModel):
    status: str | None = None
    confidence: float | None = None


class CompanyAddress(DiscolikeModel):
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    country: str | None = None


class CompanyProfile(DiscolikeModel):
    """Business data profile returned by the discover, bizdata, and match endpoints."""

    domain: str | None = None
    name: str | None = None
    status: CompanyStatus | None = None
    score: int | None = None
    start_date: str | None = None
    end_date: str | None = None
    address: CompanyAddress | None = None
    phones: list[str] | None = None
    public_emails: list[str] | None = None
    domain_associations: list[str] = pydantic.Field(default_factory=list)
    social_urls: list[str] | None = None
    redirect_domain: str | None = None
    description: str | None = None
    keywords: dict[str, float] = pydantic.Field(default_factory=dict)
    industry_groups: dict[str, float] = pydantic.Field(default_factory=dict)
    employees: str | None = None
    revenue_range: str | None = None
    business_model: dict[str, float] = pydantic.Field(default_factory=dict)
    update_date: str | None = None
    mx_provider: str | None = None
    linkup: None = None


class BizData(CompanyProfile):
    pass


class ScoreParameters(DiscolikeModel):
    base_score: float | None = None
    recency_multiplier: float | None = None
    growth_boost: float | None = None
    lookback_360: int | None = None
    lookback_720: int | None = None


class Score(DiscolikeModel):
    domain: str | None = None
    score: int | None = None
    parameters: ScoreParameters | None = None
    first_event: str | None = None


class Growth(DiscolikeModel):
    domain: str | None = None
    score_growth_3m: float | None = None
    subdomain_growth_3m: float | None = None


class ExtractResult(DiscolikeModel):
    text: str | None = None
    language: str | None = None


class Redirect(DiscolikeModel):
    source_domain: str | None = None
    source_fqdn: str | None = None
    linked_domain: str | None = None
    linked_fqdn: str | None = None
    record_date: str | None = None


class Vendor(DiscolikeModel):
    client_domain: str | None = None
    client_fqdn: str | None = None
    vendor_domain: str | None = None
    vendor_fqdn: str | None = None
    record_date: str | None = None


class Subsidiary(DiscolikeModel):
    source_domain: str | None = None
    source_fqdn: str | None = None
    source_score: int | None = None
    linked_domain: str | None = None
    linked_fqdn: str | None = None
    linked_score: int | None = None
    parent_domain: str | None = None
    child_domain: str | None = None
    record_date: str | None = None


class PublicLink(DiscolikeModel):
    domain: str | None = None
    linked_domain: str | None = None
    link_values: list[str] = pydantic.Field(default_factory=list)
    record_date: str | None = None


class CompaniesResource(SyncAPIResource):
    @api_route("GET", "/bizdata")
    def data(self, *, domain: str) -> BizData:
        params = {k: v for k, v in locals().items() if k != "self"}
        return BizData.model_validate(self._transport.request("GET", "/bizdata", params=params).json())

    @api_route("GET", "/score")
    def score(self, *, domain: str) -> Score:
        params = {k: v for k, v in locals().items() if k != "self"}
        return Score.model_validate(self._transport.request("GET", "/score", params=params).json())

    @api_route("GET", "/growth")
    def growth(self, *, domain: str) -> Growth:
        params = {k: v for k, v in locals().items() if k != "self"}
        return Growth.model_validate(self._transport.request("GET", "/growth", params=params).json())

    @api_route("GET", "/extract")
    def extract(self, *, url: str | None = None, domain: str | None = None) -> ExtractResult:
        params = {k: v for k, v in locals().items() if k != "self"}
        return ExtractResult.model_validate(self._transport.request("GET", "/extract", params=params).json())

    @api_route("GET", "/redirects")
    def redirects(self, *, domain: str, match: str | None = None) -> list[Redirect]:
        params = {k: v for k, v in locals().items() if k != "self"}
        rows = self._transport.request("GET", "/redirects", params=params).json()
        return [Redirect.model_validate(row) for row in rows]

    @api_route("GET", "/vendors")
    def vendors(self, *, domain: str, match: str | None = None) -> list[Vendor]:
        params = {k: v for k, v in locals().items() if k != "self"}
        rows = self._transport.request("GET", "/vendors", params=params).json()
        return [Vendor.model_validate(row) for row in rows]

    @api_route("GET", "/subsidiaries")
    def subsidiaries(self, *, domain: str, match: str | None = None) -> list[Subsidiary]:
        params = {k: v for k, v in locals().items() if k != "self"}
        rows = self._transport.request("GET", "/subsidiaries", params=params).json()
        return [Subsidiary.model_validate(row) for row in rows]

    @api_route("GET", "/publiclink")
    def public_links(self, *, domain: str, source: str) -> list[PublicLink]:
        params = {k: v for k, v in locals().items() if k != "self"}
        rows = self._transport.request("GET", "/publiclink", params=params).json()
        return [PublicLink.model_validate(row) for row in rows]


class AsyncCompaniesResource(AsyncAPIResource):
    @api_route("GET", "/bizdata")
    async def data(self, *, domain: str) -> BizData:
        params = {k: v for k, v in locals().items() if k != "self"}
        return BizData.model_validate((await self._transport.request("GET", "/bizdata", params=params)).json())

    @api_route("GET", "/score")
    async def score(self, *, domain: str) -> Score:
        params = {k: v for k, v in locals().items() if k != "self"}
        return Score.model_validate((await self._transport.request("GET", "/score", params=params)).json())

    @api_route("GET", "/growth")
    async def growth(self, *, domain: str) -> Growth:
        params = {k: v for k, v in locals().items() if k != "self"}
        return Growth.model_validate((await self._transport.request("GET", "/growth", params=params)).json())

    @api_route("GET", "/extract")
    async def extract(self, *, url: str | None = None, domain: str | None = None) -> ExtractResult:
        params = {k: v for k, v in locals().items() if k != "self"}
        return ExtractResult.model_validate((await self._transport.request("GET", "/extract", params=params)).json())

    @api_route("GET", "/redirects")
    async def redirects(self, *, domain: str, match: str | None = None) -> list[Redirect]:
        params = {k: v for k, v in locals().items() if k != "self"}
        rows = (await self._transport.request("GET", "/redirects", params=params)).json()
        return [Redirect.model_validate(row) for row in rows]

    @api_route("GET", "/vendors")
    async def vendors(self, *, domain: str, match: str | None = None) -> list[Vendor]:
        params = {k: v for k, v in locals().items() if k != "self"}
        rows = (await self._transport.request("GET", "/vendors", params=params)).json()
        return [Vendor.model_validate(row) for row in rows]

    @api_route("GET", "/subsidiaries")
    async def subsidiaries(self, *, domain: str, match: str | None = None) -> list[Subsidiary]:
        params = {k: v for k, v in locals().items() if k != "self"}
        rows = (await self._transport.request("GET", "/subsidiaries", params=params)).json()
        return [Subsidiary.model_validate(row) for row in rows]

    @api_route("GET", "/publiclink")
    async def public_links(self, *, domain: str, source: str) -> list[PublicLink]:
        params = {k: v for k, v in locals().items() if k != "self"}
        rows = (await self._transport.request("GET", "/publiclink", params=params)).json()
        return [PublicLink.model_validate(row) for row in rows]
