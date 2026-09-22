from __future__ import annotations

import httpx2
import pydantic

from discolike._jobs import FAMILY_DISCOGEN
from discolike._jobs import AsyncJob
from discolike._jobs import Job
from discolike._models import DiscolikeModel
from discolike._transport import AsyncTransport
from discolike._transport import Transport
from discolike.requests import DiscoGenPersonaProcessRequest
from discolike.requests import DiscoGenProcessRequest
from discolike.requests import ValidateIcpRequest
from discolike.resources._base import AsyncAPIResource
from discolike.resources._base import SyncAPIResource
from discolike.resources._base import api_route

NATIVE_ICP_ENGINE = "native-icp"


def _job(transport: Transport, response: httpx2.Response) -> Job:
    payload = response.json()
    return Job(
        transport,
        task_family=FAMILY_DISCOGEN,
        task_id=payload["task_id"],
        column_name=payload.get("column_name"),
    )


def _async_job(transport: AsyncTransport, response: httpx2.Response) -> AsyncJob:
    payload = response.json()
    return AsyncJob(
        transport,
        task_family=FAMILY_DISCOGEN,
        task_id=payload["task_id"],
        column_name=payload.get("column_name"),
    )


class DiscogenModelInfo(DiscolikeModel):
    name: str | None = None
    supports_web_search: bool | None = None


class DiscogenModels(DiscolikeModel):
    models: dict[str, list[DiscogenModelInfo]] = pydantic.Field(default_factory=dict)


class DiscogenResource(SyncAPIResource):
    @api_route("POST", "/discogen/process")
    def process(self, request: DiscoGenProcessRequest) -> Job:
        """Run a research prompt against a list of domains.

        `integration_id` takes an LLM provider integration UUID, or `NATIVE_ICP_ENGINE` to score
        an ICP validation prompt with DiscoLike's own model. Omit it for the org default.
        """
        return _job(self._transport, self._transport.request("POST", "/discogen/process", json_body=request.to_wire()))

    @api_route("POST", "/discogen/process-personas")
    def process_personas(self, request: DiscoGenPersonaProcessRequest) -> Job:
        response = self._transport.request("POST", "/discogen/process-personas", json_body=request.to_wire())
        return _job(self._transport, response)

    @api_route("GET", "/discogen/models")
    def models(self) -> DiscogenModels:
        return DiscogenModels.model_validate(self._transport.request("GET", "/discogen/models").json())

    def job(self, task_id: str) -> Job:
        return Job(self._transport, task_family=FAMILY_DISCOGEN, task_id=task_id)


class ValidateResource(SyncAPIResource):
    @api_route("POST", "/validate/icp")
    def icp(self, request: ValidateIcpRequest) -> Job:
        """Validate domains against an ICP description.

        `integration_id` takes an LLM provider integration UUID, or `NATIVE_ICP_ENGINE` to score
        with DiscoLike's own ICP-fit model: no LLM key, no LLM cost, and no web search on that
        run. Omit it for the org default. Read `Job.column_name` for the columns the run returns
        rather than assuming the LLM ones; the native run's `Reasoning` column is always null,
        since the model returns a score rather than an explanation.
        """
        return _job(self._transport, self._transport.request("POST", "/validate/icp", json_body=request.to_wire()))


class AsyncDiscogenResource(AsyncAPIResource):
    @api_route("POST", "/discogen/process")
    async def process(self, request: DiscoGenProcessRequest) -> AsyncJob:
        """Run a research prompt against a list of domains.

        `integration_id` takes an LLM provider integration UUID, or `NATIVE_ICP_ENGINE` to score
        an ICP validation prompt with DiscoLike's own model. Omit it for the org default.
        """
        response = await self._transport.request("POST", "/discogen/process", json_body=request.to_wire())
        return _async_job(self._transport, response)

    @api_route("POST", "/discogen/process-personas")
    async def process_personas(self, request: DiscoGenPersonaProcessRequest) -> AsyncJob:
        response = await self._transport.request("POST", "/discogen/process-personas", json_body=request.to_wire())
        return _async_job(self._transport, response)

    @api_route("GET", "/discogen/models")
    async def models(self) -> DiscogenModels:
        response = await self._transport.request("GET", "/discogen/models")
        return DiscogenModels.model_validate(response.json())

    def job(self, task_id: str) -> AsyncJob:
        return AsyncJob(self._transport, task_family=FAMILY_DISCOGEN, task_id=task_id)


class AsyncValidateResource(AsyncAPIResource):
    @api_route("POST", "/validate/icp")
    async def icp(self, request: ValidateIcpRequest) -> AsyncJob:
        """Validate domains against an ICP description.

        `integration_id` takes an LLM provider integration UUID, or `NATIVE_ICP_ENGINE` to score
        with DiscoLike's own ICP-fit model: no LLM key, no LLM cost, and no web search on that
        run. Omit it for the org default. Read `AsyncJob.column_name` for the columns the run
        returns rather than assuming the LLM ones; the native run's `Reasoning` column is always
        null, since the model returns a score rather than an explanation.
        """
        response = await self._transport.request("POST", "/validate/icp", json_body=request.to_wire())
        return _async_job(self._transport, response)
