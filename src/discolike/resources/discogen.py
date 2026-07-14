from __future__ import annotations

from discolike._jobs import FAMILY_DISCOGEN
from discolike._jobs import AsyncJob
from discolike._jobs import Job
from discolike._models import DiscolikeModel
from discolike._transport import drop_none
from discolike.resources._base import AsyncAPIResource
from discolike.resources._base import SyncAPIResource
from discolike.resources._base import api_route


class DiscogenModels(DiscolikeModel):
    pass


class DiscogenResource(SyncAPIResource):
    @api_route("POST", "/discogen/process")
    def process(
        self,
        *,
        query: str,
        domains: list[str],
        integration_id: str | None = None,
        web_search: bool | None = None,
        context_mode: str | None = None,
        include_x_search: bool | None = None,
        search_provider_id: str | None = None,
        search_context_size: str | None = None,
    ) -> Job:
        body = {k: v for k, v in locals().items() if k != "self"}
        response = self._transport.request("POST", "/discogen/process", json_body=drop_none(body))
        return Job(self._transport, task_family=FAMILY_DISCOGEN, task_id=response.json()["task_id"])

    @api_route("POST", "/discogen/process-personas")
    def process_personas(
        self,
        *,
        query: str,
        persona_ids: list[int],
        integration_id: str | None = None,
        web_search: bool | None = None,
        context_mode: str | None = None,
        include_x_search: bool | None = None,
        search_provider_id: str | None = None,
        search_context_size: str | None = None,
    ) -> Job:
        body = {k: v for k, v in locals().items() if k != "self"}
        response = self._transport.request("POST", "/discogen/process-personas", json_body=drop_none(body))
        return Job(self._transport, task_family=FAMILY_DISCOGEN, task_id=response.json()["task_id"])

    @api_route("GET", "/discogen/models")
    def models(self) -> DiscogenModels:
        return DiscogenModels.model_validate(self._transport.request("GET", "/discogen/models").json())

    def job(self, task_id: str) -> Job:
        return Job(self._transport, task_family=FAMILY_DISCOGEN, task_id=task_id)


class ValidateResource(SyncAPIResource):
    @api_route("POST", "/validate/icp")
    def icp(
        self,
        *,
        icp_text: str,
        domains: list[str],
        context_mode: str | None = None,
        integration_id: str | None = None,
        web_search: bool | None = None,
        search_provider_id: str | None = None,
    ) -> Job:
        body = {k: v for k, v in locals().items() if k != "self"}
        response = self._transport.request("POST", "/validate/icp", json_body=drop_none(body))
        return Job(self._transport, task_family=FAMILY_DISCOGEN, task_id=response.json()["task_id"])


class AsyncDiscogenResource(AsyncAPIResource):
    @api_route("POST", "/discogen/process")
    async def process(
        self,
        *,
        query: str,
        domains: list[str],
        integration_id: str | None = None,
        web_search: bool | None = None,
        context_mode: str | None = None,
        include_x_search: bool | None = None,
        search_provider_id: str | None = None,
        search_context_size: str | None = None,
    ) -> AsyncJob:
        body = {k: v for k, v in locals().items() if k != "self"}
        response = await self._transport.request("POST", "/discogen/process", json_body=drop_none(body))
        return AsyncJob(self._transport, task_family=FAMILY_DISCOGEN, task_id=response.json()["task_id"])

    @api_route("POST", "/discogen/process-personas")
    async def process_personas(
        self,
        *,
        query: str,
        persona_ids: list[int],
        integration_id: str | None = None,
        web_search: bool | None = None,
        context_mode: str | None = None,
        include_x_search: bool | None = None,
        search_provider_id: str | None = None,
        search_context_size: str | None = None,
    ) -> AsyncJob:
        body = {k: v for k, v in locals().items() if k != "self"}
        response = await self._transport.request("POST", "/discogen/process-personas", json_body=drop_none(body))
        return AsyncJob(self._transport, task_family=FAMILY_DISCOGEN, task_id=response.json()["task_id"])

    @api_route("GET", "/discogen/models")
    async def models(self) -> DiscogenModels:
        response = await self._transport.request("GET", "/discogen/models")
        return DiscogenModels.model_validate(response.json())

    def job(self, task_id: str) -> AsyncJob:
        return AsyncJob(self._transport, task_family=FAMILY_DISCOGEN, task_id=task_id)


class AsyncValidateResource(AsyncAPIResource):
    @api_route("POST", "/validate/icp")
    async def icp(
        self,
        *,
        icp_text: str,
        domains: list[str],
        context_mode: str | None = None,
        integration_id: str | None = None,
        web_search: bool | None = None,
        search_provider_id: str | None = None,
    ) -> AsyncJob:
        body = {k: v for k, v in locals().items() if k != "self"}
        response = await self._transport.request("POST", "/validate/icp", json_body=drop_none(body))
        return AsyncJob(self._transport, task_family=FAMILY_DISCOGEN, task_id=response.json()["task_id"])
