from __future__ import annotations

import pydantic

from discolike._jobs import FAMILY_DISCOGEN
from discolike._jobs import AsyncJob
from discolike._jobs import Job
from discolike._models import DiscolikeModel
from discolike.requests import DiscoGenPersonaProcessRequest
from discolike.requests import DiscoGenProcessRequest
from discolike.requests import ValidateIcpRequest
from discolike.resources._base import AsyncAPIResource
from discolike.resources._base import SyncAPIResource
from discolike.resources._base import api_route


class DiscogenModelInfo(DiscolikeModel):
    name: str | None = None
    supports_web_search: bool | None = None


class DiscogenModels(DiscolikeModel):
    models: dict[str, list[DiscogenModelInfo]] = pydantic.Field(default_factory=dict)


class DiscogenResource(SyncAPIResource):
    @api_route("POST", "/discogen/process")
    def process(self, request: DiscoGenProcessRequest) -> Job:
        response = self._transport.request("POST", "/discogen/process", json_body=request.to_wire())
        return Job(self._transport, task_family=FAMILY_DISCOGEN, task_id=response.json()["task_id"])

    @api_route("POST", "/discogen/process-personas")
    def process_personas(self, request: DiscoGenPersonaProcessRequest) -> Job:
        response = self._transport.request("POST", "/discogen/process-personas", json_body=request.to_wire())
        return Job(self._transport, task_family=FAMILY_DISCOGEN, task_id=response.json()["task_id"])

    @api_route("GET", "/discogen/models")
    def models(self) -> DiscogenModels:
        return DiscogenModels.model_validate(self._transport.request("GET", "/discogen/models").json())

    def job(self, task_id: str) -> Job:
        return Job(self._transport, task_family=FAMILY_DISCOGEN, task_id=task_id)


class ValidateResource(SyncAPIResource):
    @api_route("POST", "/validate/icp")
    def icp(self, request: ValidateIcpRequest) -> Job:
        response = self._transport.request("POST", "/validate/icp", json_body=request.to_wire())
        return Job(self._transport, task_family=FAMILY_DISCOGEN, task_id=response.json()["task_id"])


class AsyncDiscogenResource(AsyncAPIResource):
    @api_route("POST", "/discogen/process")
    async def process(self, request: DiscoGenProcessRequest) -> AsyncJob:
        response = await self._transport.request("POST", "/discogen/process", json_body=request.to_wire())
        return AsyncJob(self._transport, task_family=FAMILY_DISCOGEN, task_id=response.json()["task_id"])

    @api_route("POST", "/discogen/process-personas")
    async def process_personas(self, request: DiscoGenPersonaProcessRequest) -> AsyncJob:
        response = await self._transport.request("POST", "/discogen/process-personas", json_body=request.to_wire())
        return AsyncJob(self._transport, task_family=FAMILY_DISCOGEN, task_id=response.json()["task_id"])

    @api_route("GET", "/discogen/models")
    async def models(self) -> DiscogenModels:
        response = await self._transport.request("GET", "/discogen/models")
        return DiscogenModels.model_validate(response.json())

    def job(self, task_id: str) -> AsyncJob:
        return AsyncJob(self._transport, task_family=FAMILY_DISCOGEN, task_id=task_id)


class AsyncValidateResource(AsyncAPIResource):
    @api_route("POST", "/validate/icp")
    async def icp(self, request: ValidateIcpRequest) -> AsyncJob:
        response = await self._transport.request("POST", "/validate/icp", json_body=request.to_wire())
        return AsyncJob(self._transport, task_family=FAMILY_DISCOGEN, task_id=response.json()["task_id"])
