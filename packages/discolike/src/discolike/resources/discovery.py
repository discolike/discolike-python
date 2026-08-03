from __future__ import annotations

from discolike._models import DiscolikeModel
from discolike.resources._base import AsyncAPIResource
from discolike.resources._base import SyncAPIResource
from discolike.resources._base import api_route
from discolike.resources.companies import CompanyProfile


class Company(CompanyProfile):
    similarity: float | None = None


class Count(DiscolikeModel):
    count: int | None = None


class DiscoveryResource(SyncAPIResource):
    @api_route("GET", "/discover")
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
        params = {k: v for k, v in locals().items() if k != "self"}
        response = self._transport.request("GET", "/discover", params=params)
        return [Company.model_validate(item) for item in response.json()]

    @api_route("GET", "/count")
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
        params = {k: v for k, v in locals().items() if k != "self"}
        return Count.model_validate(self._transport.request("GET", "/count", params=params).json())


class AsyncDiscoveryResource(AsyncAPIResource):
    @api_route("GET", "/discover")
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
        params = {k: v for k, v in locals().items() if k != "self"}
        response = await self._transport.request("GET", "/discover", params=params)
        return [Company.model_validate(item) for item in response.json()]

    @api_route("GET", "/count")
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
        params = {k: v for k, v in locals().items() if k != "self"}
        response = await self._transport.request("GET", "/count", params=params)
        return Count.model_validate(response.json())
