from __future__ import annotations

from discolike._models import DiscolikeModel
from discolike.resources._base import AsyncAPIResource
from discolike.resources._base import SyncAPIResource
from discolike.resources._base import api_route


class Usage(DiscolikeModel):
    requests_mtd: int | None = None
    records_mtd: int | None = None
    spend_mtd: float | None = None


class AccountResource(SyncAPIResource):
    @api_route("GET", "/usage")
    def usage(self) -> Usage:
        return Usage.model_validate(self._transport.request("GET", "/usage").json())


class AsyncAccountResource(AsyncAPIResource):
    @api_route("GET", "/usage")
    async def usage(self) -> Usage:
        return Usage.model_validate((await self._transport.request("GET", "/usage")).json())
