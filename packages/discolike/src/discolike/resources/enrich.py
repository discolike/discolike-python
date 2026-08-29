from __future__ import annotations

from discolike._jobs import FAMILY_SEGMENT
from discolike._jobs import AsyncJob
from discolike._jobs import Job
from discolike._models import DiscolikeModel
from discolike.requests import AppendParams
from discolike.requests import SegmentFileParams
from discolike.requests import SegmentParams
from discolike.resources._base import AsyncAPIResource
from discolike.resources._base import FileInput
from discolike.resources._base import SyncAPIResource
from discolike.resources._base import api_route
from discolike.resources._base import open_upload

JSON_CONTENT_TYPE = "application/json"


class AppendResult(DiscolikeModel):
    domain: str | None = None


class EnrichResource(SyncAPIResource):
    @api_route("POST", "/append")
    def append(self, params: AppendParams, *, file: FileInput | None = None) -> list[AppendResult] | bytes:
        if file is None and not params.query_id:
            raise ValueError("one of file or query_id is required")
        if file is None:
            response = self._transport.request("POST", "/append", params=params.to_wire())
        else:
            filename, fh, we_opened_it = open_upload(file)
            try:
                response = self._transport.request(
                    "POST", "/append", params=params.to_wire(), files={"file": (filename, fh)}
                )
            finally:
                if we_opened_it:
                    fh.close()
        if JSON_CONTENT_TYPE in response.headers.get("Content-Type", ""):
            return [AppendResult.model_validate(item) for item in response.json()]
        return response.content

    @api_route("GET", "/segment")
    def segment(self, params: SegmentParams) -> Job:
        if not params.domains and not params.query_id:
            raise ValueError("one of domains or query_id is required")
        response = self._transport.request("GET", "/segment", params=params.to_wire())
        return Job(self._transport, task_family=FAMILY_SEGMENT, task_id=response.json()["task_id"])

    @api_route("POST", "/segment")
    def segment_file(self, params: SegmentFileParams, *, file: FileInput) -> Job:
        filename, fh, we_opened_it = open_upload(file)
        try:
            response = self._transport.request(
                "POST", "/segment", params=params.to_wire(), files={"file": (filename, fh)}
            )
        finally:
            if we_opened_it:
                fh.close()
        return Job(self._transport, task_family=FAMILY_SEGMENT, task_id=response.json()["task_id"])


class AsyncEnrichResource(AsyncAPIResource):
    @api_route("POST", "/append")
    async def append(self, params: AppendParams, *, file: FileInput | None = None) -> list[AppendResult] | bytes:
        if file is None and not params.query_id:
            raise ValueError("one of file or query_id is required")
        if file is None:
            response = await self._transport.request("POST", "/append", params=params.to_wire())
        else:
            filename, fh, we_opened_it = open_upload(file)
            try:
                response = await self._transport.request(
                    "POST", "/append", params=params.to_wire(), files={"file": (filename, fh)}
                )
            finally:
                if we_opened_it:
                    fh.close()
        if JSON_CONTENT_TYPE in response.headers.get("Content-Type", ""):
            return [AppendResult.model_validate(item) for item in response.json()]
        return response.content

    @api_route("GET", "/segment")
    async def segment(self, params: SegmentParams) -> AsyncJob:
        if not params.domains and not params.query_id:
            raise ValueError("one of domains or query_id is required")
        response = await self._transport.request("GET", "/segment", params=params.to_wire())
        return AsyncJob(self._transport, task_family=FAMILY_SEGMENT, task_id=response.json()["task_id"])

    @api_route("POST", "/segment")
    async def segment_file(self, params: SegmentFileParams, *, file: FileInput) -> AsyncJob:
        filename, fh, we_opened_it = open_upload(file)
        try:
            response = await self._transport.request(
                "POST", "/segment", params=params.to_wire(), files={"file": (filename, fh)}
            )
        finally:
            if we_opened_it:
                fh.close()
        return AsyncJob(self._transport, task_family=FAMILY_SEGMENT, task_id=response.json()["task_id"])
