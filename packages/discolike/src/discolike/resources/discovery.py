from __future__ import annotations

from discolike._models import DiscolikeModel
from discolike.requests import CountParams
from discolike.requests import DiscoverParams
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
    def discover(self, params: DiscoverParams) -> list[Company]:
        response = self._transport.request("GET", "/discover", params=params.to_wire())
        return [Company.model_validate(item) for item in response.json()]

    @api_route("GET", "/count")
    def count(self, params: CountParams) -> Count:
        return Count.model_validate(self._transport.request("GET", "/count", params=params.to_wire()).json())


class AsyncDiscoveryResource(AsyncAPIResource):
    @api_route("GET", "/discover")
    async def discover(self, params: DiscoverParams) -> list[Company]:
        response = await self._transport.request("GET", "/discover", params=params.to_wire())
        return [Company.model_validate(item) for item in response.json()]

    @api_route("GET", "/count")
    async def count(self, params: CountParams) -> Count:
        response = await self._transport.request("GET", "/count", params=params.to_wire())
        return Count.model_validate(response.json())
