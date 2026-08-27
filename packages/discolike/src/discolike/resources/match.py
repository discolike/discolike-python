from __future__ import annotations

import pydantic

from discolike._jobs import FAMILY_BULKMATCH
from discolike._jobs import AsyncJob
from discolike._jobs import Job
from discolike._models import DiscolikeModel
from discolike.requests import MatchBulkParams
from discolike.requests import MatchCompanyParams
from discolike.resources._base import AsyncAPIResource
from discolike.resources._base import FileInput
from discolike.resources._base import SyncAPIResource
from discolike.resources._base import api_route
from discolike.resources._base import open_upload
from discolike.resources.companies import CompanyProfile


class MatchQuery(DiscolikeModel):
    name: str | None = None
    country: str | None = None
    state: str | None = None
    city: str | None = None
    zip: str | None = None
    phones: str | None = None


class MatchResult(CompanyProfile):
    match_confidence: float | None = None


class MatchResponse(DiscolikeModel):
    query: MatchQuery | None = None
    matches: list[MatchResult] = pydantic.Field(default_factory=list)


class MatchResource(SyncAPIResource):
    @api_route("GET", "/match")
    def company(self, params: MatchCompanyParams) -> MatchResponse:
        return MatchResponse.model_validate(self._transport.request("GET", "/match", params=params.to_wire()).json())

    @api_route("POST", "/bulkmatch")
    def bulk(self, params: MatchBulkParams, *, file: FileInput) -> Job:
        filename, fh, we_opened_it = open_upload(file)
        try:
            response = self._transport.request(
                "POST", "/bulkmatch", params=params.to_wire(), files={"file": (filename, fh)}
            )
        finally:
            if we_opened_it:
                fh.close()
        return Job(self._transport, task_family=FAMILY_BULKMATCH, task_id=response.json()["task_id"])


class AsyncMatchResource(AsyncAPIResource):
    @api_route("GET", "/match")
    async def company(self, params: MatchCompanyParams) -> MatchResponse:
        response = await self._transport.request("GET", "/match", params=params.to_wire())
        return MatchResponse.model_validate(response.json())

    @api_route("POST", "/bulkmatch")
    async def bulk(self, params: MatchBulkParams, *, file: FileInput) -> AsyncJob:
        filename, fh, we_opened_it = open_upload(file)
        try:
            response = await self._transport.request(
                "POST", "/bulkmatch", params=params.to_wire(), files={"file": (filename, fh)}
            )
        finally:
            if we_opened_it:
                fh.close()
        return AsyncJob(self._transport, task_family=FAMILY_BULKMATCH, task_id=response.json()["task_id"])
