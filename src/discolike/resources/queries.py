from __future__ import annotations

import builtins

from discolike._models import DiscolikeModel
from discolike._transport import drop_none
from discolike.resources._base import AsyncAPIResource, SyncAPIResource, api_route


class SavedQueries(DiscolikeModel):
    pass


class QueryResult(DiscolikeModel):
    query_id: str | None = None
    query_name: str | None = None


class QueriesResource(SyncAPIResource):
    @api_route("GET", "/queries/saved")
    def list(
        self,
        *,
        max_records: int | None = None,
        offset: int | None = None,
        action: str | None = None,
        tags: builtins.list[str] | None = None,
    ) -> SavedQueries:
        params = {k: v for k, v in locals().items() if k != "self"}
        return SavedQueries.model_validate(self._transport.request("GET", "/queries/saved", params=params).json())

    @api_route("POST", "/queries/exclusion-list")
    def create_exclusion_list(
        self,
        *,
        query_name: str,
        domains: builtins.list[str] | None = None,
        persona_ids: builtins.list[int] | None = None,
        tags: builtins.list[str] | None = None,
    ) -> QueryResult:
        body = {k: v for k, v in locals().items() if k != "self"}
        response = self._transport.request("POST", "/queries/exclusion-list", json_body=drop_none(body))
        return QueryResult.model_validate(response.json())

    @api_route("PATCH", "/queries/{query_id}")
    def update(
        self,
        *,
        query_id: str,
        query_name: str | None = None,
        tags: builtins.list[str] | None = None,
    ) -> QueryResult:
        body = {"query_name": query_name, "tags": tags}
        response = self._transport.request("PATCH", f"/queries/{query_id}", json_body=drop_none(body))
        return QueryResult.model_validate(response.json())

    @api_route("DELETE", "/queries/{query_id}")
    def delete(self, *, query_id: str) -> None:
        self._transport.request("DELETE", f"/queries/{query_id}")


class AsyncQueriesResource(AsyncAPIResource):
    @api_route("GET", "/queries/saved")
    async def list(
        self,
        *,
        max_records: int | None = None,
        offset: int | None = None,
        action: str | None = None,
        tags: builtins.list[str] | None = None,
    ) -> SavedQueries:
        params = {k: v for k, v in locals().items() if k != "self"}
        response = await self._transport.request("GET", "/queries/saved", params=params)
        return SavedQueries.model_validate(response.json())

    @api_route("POST", "/queries/exclusion-list")
    async def create_exclusion_list(
        self,
        *,
        query_name: str,
        domains: builtins.list[str] | None = None,
        persona_ids: builtins.list[int] | None = None,
        tags: builtins.list[str] | None = None,
    ) -> QueryResult:
        body = {k: v for k, v in locals().items() if k != "self"}
        response = await self._transport.request("POST", "/queries/exclusion-list", json_body=drop_none(body))
        return QueryResult.model_validate(response.json())

    @api_route("PATCH", "/queries/{query_id}")
    async def update(
        self,
        *,
        query_id: str,
        query_name: str | None = None,
        tags: builtins.list[str] | None = None,
    ) -> QueryResult:
        body = {"query_name": query_name, "tags": tags}
        response = await self._transport.request("PATCH", f"/queries/{query_id}", json_body=drop_none(body))
        return QueryResult.model_validate(response.json())

    @api_route("DELETE", "/queries/{query_id}")
    async def delete(self, *, query_id: str) -> None:
        await self._transport.request("DELETE", f"/queries/{query_id}")
