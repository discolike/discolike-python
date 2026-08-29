from __future__ import annotations

import builtins

import pydantic

from discolike._models import DiscolikeModel
from discolike.requests import CreateExclusionListRequest
from discolike.requests import QueriesListParams
from discolike.requests import SaveResultsRequest
from discolike.requests import UpdateQueryRequest
from discolike.resources._base import AsyncAPIResource
from discolike.resources._base import SyncAPIResource
from discolike.resources._base import api_route


class SavedQuery(DiscolikeModel):
    query_id: str | None = None
    query_name: str | None = None
    action: str | None = None
    user_name: str | None = None
    mtime: str | None = None
    domains: builtins.list[str] | None = None
    domain_count: int | None = None
    persona_id_count: int | None = None
    tags: builtins.list[str] = pydantic.Field(default_factory=list)


class SavedQueries(DiscolikeModel):
    results: builtins.list[SavedQuery] = pydantic.Field(default_factory=list)
    count: int | None = None


class QueryResult(DiscolikeModel):
    query_id: str | None = None
    query_name: str | None = None
    action: str | None = None
    domain_count: int | None = None
    persona_id_count: int | None = None
    row_count: int | None = None
    tags: builtins.list[str] | None = None


class QueriesResource(SyncAPIResource):
    @api_route("GET", "/queries/saved")
    def list(self, params: QueriesListParams) -> SavedQueries:
        response = self._transport.request("GET", "/queries/saved", params=params.to_wire())
        return SavedQueries.model_validate(response.json())

    @api_route("POST", "/queries/exclusion-list")
    def create_exclusion_list(self, request: CreateExclusionListRequest) -> QueryResult:
        response = self._transport.request("POST", "/queries/exclusion-list", json_body=request.to_wire())
        return QueryResult.model_validate(response.json())

    @api_route("POST", "/queries/save-results")
    def save_results(self, request: SaveResultsRequest) -> QueryResult:
        response = self._transport.request("POST", "/queries/save-results", json_body=request.to_wire())
        return QueryResult.model_validate(response.json())

    @api_route("PATCH", "/queries/{query_id}")
    def update(self, request: UpdateQueryRequest, *, query_id: str) -> QueryResult:
        response = self._transport.request("PATCH", f"/queries/{query_id}", json_body=request.to_wire())
        return QueryResult.model_validate(response.json())

    @api_route("DELETE", "/queries/{query_id}")
    def delete(self, *, query_id: str) -> None:
        self._transport.request("DELETE", f"/queries/{query_id}")


class AsyncQueriesResource(AsyncAPIResource):
    @api_route("GET", "/queries/saved")
    async def list(self, params: QueriesListParams) -> SavedQueries:
        response = await self._transport.request("GET", "/queries/saved", params=params.to_wire())
        return SavedQueries.model_validate(response.json())

    @api_route("POST", "/queries/exclusion-list")
    async def create_exclusion_list(self, request: CreateExclusionListRequest) -> QueryResult:
        response = await self._transport.request("POST", "/queries/exclusion-list", json_body=request.to_wire())
        return QueryResult.model_validate(response.json())

    @api_route("POST", "/queries/save-results")
    async def save_results(self, request: SaveResultsRequest) -> QueryResult:
        response = await self._transport.request("POST", "/queries/save-results", json_body=request.to_wire())
        return QueryResult.model_validate(response.json())

    @api_route("PATCH", "/queries/{query_id}")
    async def update(self, request: UpdateQueryRequest, *, query_id: str) -> QueryResult:
        response = await self._transport.request("PATCH", f"/queries/{query_id}", json_body=request.to_wire())
        return QueryResult.model_validate(response.json())

    @api_route("DELETE", "/queries/{query_id}")
    async def delete(self, *, query_id: str) -> None:
        await self._transport.request("DELETE", f"/queries/{query_id}")
