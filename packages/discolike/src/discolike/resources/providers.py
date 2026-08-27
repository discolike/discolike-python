from __future__ import annotations

import pydantic

from discolike._models import DiscolikeModel
from discolike.requests import LLMProviderCreateRequest
from discolike.requests import LLMProviderUpdateRequest
from discolike.requests import SearchProviderRequest
from discolike.resources._base import AsyncAPIResource
from discolike.resources._base import SyncAPIResource
from discolike.resources._base import api_route


class SearchProviderList(DiscolikeModel):
    providers: list[SearchProviderConfig] = pydantic.Field(default_factory=list)


class SearchProviderConfig(DiscolikeModel):
    integration_id: str | None = None
    integration_name: str | None = None


class SearchProviderResult(DiscolikeModel):
    message: str | None = None
    integration_id: str | None = None


class SearchModelInfo(DiscolikeModel):
    name: str | None = None
    cost_per_query: float | None = None


class SearchModels(DiscolikeModel):
    models: dict[str, list[SearchModelInfo]] = pydantic.Field(default_factory=dict)


class LLMProviderList(DiscolikeModel):
    providers: list[LLMProviderConfig] = pydantic.Field(default_factory=list)
    mtime: str | None = None


class LLMProviderConfig(DiscolikeModel):
    integration_id: str | None = None
    integration_name: str | None = None


class LLMIntegrationResult(DiscolikeModel):
    message: str | None = None
    integration_id: str | None = None
    status: str | None = None


class SearchProvidersResource(SyncAPIResource):
    @api_route("GET", "/search-providers")
    def list(self) -> SearchProviderList:
        return SearchProviderList.model_validate(self._transport.request("GET", "/search-providers").json())

    @api_route("POST", "/search-providers")
    def create(self, request: SearchProviderRequest) -> SearchProviderConfig:
        response = self._transport.request("POST", "/search-providers", json_body=request.to_wire())
        return SearchProviderConfig.model_validate(response.json())

    @api_route("PUT", "/search-providers/{integration_id}")
    def update(self, request: SearchProviderRequest, *, integration_id: str) -> SearchProviderConfig:
        response = self._transport.request("PUT", f"/search-providers/{integration_id}", json_body=request.to_wire())
        return SearchProviderConfig.model_validate(response.json())

    @api_route("DELETE", "/search-providers/{integration_id}")
    def delete(self, *, integration_id: str) -> None:
        self._transport.request("DELETE", f"/search-providers/{integration_id}")

    @api_route("PUT", "/search-providers/{integration_id}/default")
    def set_default(self, *, integration_id: str) -> SearchProviderResult:
        response = self._transport.request("PUT", f"/search-providers/{integration_id}/default")
        return SearchProviderResult.model_validate(response.json())

    @api_route("DELETE", "/search-providers/{integration_id}/default")
    def clear_default(self, *, integration_id: str) -> SearchProviderResult:
        response = self._transport.request("DELETE", f"/search-providers/{integration_id}/default")
        return SearchProviderResult.model_validate(response.json())

    @api_route("GET", "/search-providers/models")
    def models(self) -> SearchModels:
        return SearchModels.model_validate(self._transport.request("GET", "/search-providers/models").json())


class AsyncSearchProvidersResource(AsyncAPIResource):
    @api_route("GET", "/search-providers")
    async def list(self) -> SearchProviderList:
        response = await self._transport.request("GET", "/search-providers")
        return SearchProviderList.model_validate(response.json())

    @api_route("POST", "/search-providers")
    async def create(self, request: SearchProviderRequest) -> SearchProviderConfig:
        response = await self._transport.request("POST", "/search-providers", json_body=request.to_wire())
        return SearchProviderConfig.model_validate(response.json())

    @api_route("PUT", "/search-providers/{integration_id}")
    async def update(self, request: SearchProviderRequest, *, integration_id: str) -> SearchProviderConfig:
        response = await self._transport.request(
            "PUT", f"/search-providers/{integration_id}", json_body=request.to_wire()
        )
        return SearchProviderConfig.model_validate(response.json())

    @api_route("DELETE", "/search-providers/{integration_id}")
    async def delete(self, *, integration_id: str) -> None:
        await self._transport.request("DELETE", f"/search-providers/{integration_id}")

    @api_route("PUT", "/search-providers/{integration_id}/default")
    async def set_default(self, *, integration_id: str) -> SearchProviderResult:
        response = await self._transport.request("PUT", f"/search-providers/{integration_id}/default")
        return SearchProviderResult.model_validate(response.json())

    @api_route("DELETE", "/search-providers/{integration_id}/default")
    async def clear_default(self, *, integration_id: str) -> SearchProviderResult:
        response = await self._transport.request("DELETE", f"/search-providers/{integration_id}/default")
        return SearchProviderResult.model_validate(response.json())

    @api_route("GET", "/search-providers/models")
    async def models(self) -> SearchModels:
        response = await self._transport.request("GET", "/search-providers/models")
        return SearchModels.model_validate(response.json())


class LLMProvidersResource(SyncAPIResource):
    @api_route("GET", "/llm-providers/config")
    def list(self) -> LLMProviderList:
        return LLMProviderList.model_validate(self._transport.request("GET", "/llm-providers/config").json())

    @api_route("POST", "/llm-providers/config")
    def create(self, request: LLMProviderCreateRequest) -> LLMIntegrationResult:
        response = self._transport.request("POST", "/llm-providers/config", json_body=request.to_wire())
        return LLMIntegrationResult.model_validate(response.json())

    @api_route("GET", "/llm-providers/config/{integration_id}")
    def get(self, *, integration_id: str) -> LLMProviderConfig:
        response = self._transport.request("GET", f"/llm-providers/config/{integration_id}")
        return LLMProviderConfig.model_validate(response.json())

    @api_route("PUT", "/llm-providers/config/{integration_id}")
    def update(self, request: LLMProviderUpdateRequest, *, integration_id: str) -> LLMIntegrationResult:
        response = self._transport.request(
            "PUT", f"/llm-providers/config/{integration_id}", json_body=request.to_wire()
        )
        return LLMIntegrationResult.model_validate(response.json())

    @api_route("DELETE", "/llm-providers/config/{integration_id}")
    def delete(self, *, integration_id: str) -> None:
        self._transport.request("DELETE", f"/llm-providers/config/{integration_id}")

    @api_route("POST", "/llm-providers/config/{integration_id}/set-default")
    def set_default(self, *, integration_id: str) -> LLMIntegrationResult:
        response = self._transport.request("POST", f"/llm-providers/config/{integration_id}/set-default")
        return LLMIntegrationResult.model_validate(response.json())

    @api_route("POST", "/llm-providers/test-connection")
    def test_connection(self, request: LLMProviderCreateRequest) -> LLMIntegrationResult:
        response = self._transport.request("POST", "/llm-providers/test-connection", json_body=request.to_wire())
        return LLMIntegrationResult.model_validate(response.json())


class AsyncLLMProvidersResource(AsyncAPIResource):
    @api_route("GET", "/llm-providers/config")
    async def list(self) -> LLMProviderList:
        response = await self._transport.request("GET", "/llm-providers/config")
        return LLMProviderList.model_validate(response.json())

    @api_route("POST", "/llm-providers/config")
    async def create(self, request: LLMProviderCreateRequest) -> LLMIntegrationResult:
        response = await self._transport.request("POST", "/llm-providers/config", json_body=request.to_wire())
        return LLMIntegrationResult.model_validate(response.json())

    @api_route("GET", "/llm-providers/config/{integration_id}")
    async def get(self, *, integration_id: str) -> LLMProviderConfig:
        response = await self._transport.request("GET", f"/llm-providers/config/{integration_id}")
        return LLMProviderConfig.model_validate(response.json())

    @api_route("PUT", "/llm-providers/config/{integration_id}")
    async def update(self, request: LLMProviderUpdateRequest, *, integration_id: str) -> LLMIntegrationResult:
        response = await self._transport.request(
            "PUT", f"/llm-providers/config/{integration_id}", json_body=request.to_wire()
        )
        return LLMIntegrationResult.model_validate(response.json())

    @api_route("DELETE", "/llm-providers/config/{integration_id}")
    async def delete(self, *, integration_id: str) -> None:
        await self._transport.request("DELETE", f"/llm-providers/config/{integration_id}")

    @api_route("POST", "/llm-providers/config/{integration_id}/set-default")
    async def set_default(self, *, integration_id: str) -> LLMIntegrationResult:
        response = await self._transport.request("POST", f"/llm-providers/config/{integration_id}/set-default")
        return LLMIntegrationResult.model_validate(response.json())

    @api_route("POST", "/llm-providers/test-connection")
    async def test_connection(self, request: LLMProviderCreateRequest) -> LLMIntegrationResult:
        response = await self._transport.request("POST", "/llm-providers/test-connection", json_body=request.to_wire())
        return LLMIntegrationResult.model_validate(response.json())
