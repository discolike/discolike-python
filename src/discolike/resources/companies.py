from __future__ import annotations

from discolike._models import DiscolikeModel
from discolike.resources._base import AsyncAPIResource, SyncAPIResource, api_route


class BizData(DiscolikeModel):
    pass


class Score(DiscolikeModel):
    pass


class Growth(DiscolikeModel):
    pass


class Metrics(DiscolikeModel):
    pass


class History(DiscolikeModel):
    pass


class ExtractResult(DiscolikeModel):
    pass


class Redirects(DiscolikeModel):
    pass


class Vendors(DiscolikeModel):
    pass


class Subsidiaries(DiscolikeModel):
    pass


class PublicLinks(DiscolikeModel):
    pass


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

    @api_route("GET", "/metrics")
    def metrics(self, *, domain: str) -> Metrics:
        params = {k: v for k, v in locals().items() if k != "self"}
        return Metrics.model_validate(self._transport.request("GET", "/metrics", params=params).json())

    @api_route("GET", "/history")
    def history(self, *, domain: str, max_records: int | None = None) -> History:
        params = {k: v for k, v in locals().items() if k != "self"}
        return History.model_validate(self._transport.request("GET", "/history", params=params).json())

    @api_route("GET", "/extract")
    def extract(self, *, url: str | None = None, domain: str | None = None) -> ExtractResult:
        params = {k: v for k, v in locals().items() if k != "self"}
        return ExtractResult.model_validate(self._transport.request("GET", "/extract", params=params).json())

    @api_route("GET", "/redirects")
    def redirects(self, *, domain: str, match: str | None = None) -> Redirects:
        params = {k: v for k, v in locals().items() if k != "self"}
        return Redirects.model_validate(self._transport.request("GET", "/redirects", params=params).json())

    @api_route("GET", "/vendors")
    def vendors(self, *, domain: str, match: str | None = None) -> Vendors:
        params = {k: v for k, v in locals().items() if k != "self"}
        return Vendors.model_validate(self._transport.request("GET", "/vendors", params=params).json())

    @api_route("GET", "/subsidiaries")
    def subsidiaries(self, *, domain: str, match: str | None = None) -> Subsidiaries:
        params = {k: v for k, v in locals().items() if k != "self"}
        return Subsidiaries.model_validate(self._transport.request("GET", "/subsidiaries", params=params).json())

    @api_route("GET", "/publiclink")
    def public_links(self, *, domain: str, source: str) -> PublicLinks:
        params = {k: v for k, v in locals().items() if k != "self"}
        return PublicLinks.model_validate(self._transport.request("GET", "/publiclink", params=params).json())


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

    @api_route("GET", "/metrics")
    async def metrics(self, *, domain: str) -> Metrics:
        params = {k: v for k, v in locals().items() if k != "self"}
        return Metrics.model_validate((await self._transport.request("GET", "/metrics", params=params)).json())

    @api_route("GET", "/history")
    async def history(self, *, domain: str, max_records: int | None = None) -> History:
        params = {k: v for k, v in locals().items() if k != "self"}
        return History.model_validate((await self._transport.request("GET", "/history", params=params)).json())

    @api_route("GET", "/extract")
    async def extract(self, *, url: str | None = None, domain: str | None = None) -> ExtractResult:
        params = {k: v for k, v in locals().items() if k != "self"}
        return ExtractResult.model_validate((await self._transport.request("GET", "/extract", params=params)).json())

    @api_route("GET", "/redirects")
    async def redirects(self, *, domain: str, match: str | None = None) -> Redirects:
        params = {k: v for k, v in locals().items() if k != "self"}
        return Redirects.model_validate((await self._transport.request("GET", "/redirects", params=params)).json())

    @api_route("GET", "/vendors")
    async def vendors(self, *, domain: str, match: str | None = None) -> Vendors:
        params = {k: v for k, v in locals().items() if k != "self"}
        return Vendors.model_validate((await self._transport.request("GET", "/vendors", params=params)).json())

    @api_route("GET", "/subsidiaries")
    async def subsidiaries(self, *, domain: str, match: str | None = None) -> Subsidiaries:
        params = {k: v for k, v in locals().items() if k != "self"}
        return Subsidiaries.model_validate(
            (await self._transport.request("GET", "/subsidiaries", params=params)).json()
        )

    @api_route("GET", "/publiclink")
    async def public_links(self, *, domain: str, source: str) -> PublicLinks:
        params = {k: v for k, v in locals().items() if k != "self"}
        return PublicLinks.model_validate((await self._transport.request("GET", "/publiclink", params=params)).json())
