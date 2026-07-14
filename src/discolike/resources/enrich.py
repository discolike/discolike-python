from __future__ import annotations

import pathlib
from typing import BinaryIO

from discolike._jobs import FAMILY_SEGMENT, AsyncJob, Job
from discolike._models import DiscolikeModel
from discolike.resources._base import AsyncAPIResource, SyncAPIResource, api_route, open_upload

JSON_CONTENT_TYPE = "application/json"


class AppendResult(DiscolikeModel):
    domain: str | None = None


class EnrichResource(SyncAPIResource):
    @api_route("POST", "/append")
    def append(
        self,
        *,
        file: pathlib.Path | str | BinaryIO,
        dataset: list[str] | None = None,
        domain_column: str | None = None,
        csv: bool | None = None,
    ) -> list[AppendResult] | bytes:
        params = {"dataset": dataset, "domain_column": domain_column, "csv": csv}
        filename, fh, we_opened_it = open_upload(file)
        try:
            response = self._transport.request("POST", "/append", params=params, files={"file": (filename, fh)})
        finally:
            if we_opened_it:
                fh.close()
        if JSON_CONTENT_TYPE in response.headers.get("Content-Type", ""):
            return [AppendResult.model_validate(item) for item in response.json()]
        return response.content

    @api_route("GET", "/segment")
    def segment(
        self,
        *,
        domains: list[str] | None = None,
        file: pathlib.Path | str | BinaryIO | None = None,
        domain_column: str | None = None,
        max_segments: int | None = None,
    ) -> Job:
        if (domains is None) == (file is None):
            raise ValueError("exactly one of domains or file is required")
        if domains is not None:
            params = {"domains": ",".join(domains), "max_segments": max_segments}
            response = self._transport.request("GET", "/segment", params=params)
            return Job(self._transport, task_family=FAMILY_SEGMENT, task_id=response.json()["task_id"])
        assert file is not None
        return self._segment_file(file=file, domain_column=domain_column, max_segments=max_segments)

    @api_route("POST", "/segment")
    def _segment_file(
        self,
        *,
        file: pathlib.Path | str | BinaryIO,
        domain_column: str | None,
        max_segments: int | None,
    ) -> Job:
        params = {"domain_column": domain_column, "max_segments": max_segments}
        filename, fh, we_opened_it = open_upload(file)
        try:
            response = self._transport.request("POST", "/segment", params=params, files={"file": (filename, fh)})
        finally:
            if we_opened_it:
                fh.close()
        return Job(self._transport, task_family=FAMILY_SEGMENT, task_id=response.json()["task_id"])


class AsyncEnrichResource(AsyncAPIResource):
    @api_route("POST", "/append")
    async def append(
        self,
        *,
        file: pathlib.Path | str | BinaryIO,
        dataset: list[str] | None = None,
        domain_column: str | None = None,
        csv: bool | None = None,
    ) -> list[AppendResult] | bytes:
        params = {"dataset": dataset, "domain_column": domain_column, "csv": csv}
        filename, fh, we_opened_it = open_upload(file)
        try:
            response = await self._transport.request("POST", "/append", params=params, files={"file": (filename, fh)})
        finally:
            if we_opened_it:
                fh.close()
        if JSON_CONTENT_TYPE in response.headers.get("Content-Type", ""):
            return [AppendResult.model_validate(item) for item in response.json()]
        return response.content

    @api_route("GET", "/segment")
    async def segment(
        self,
        *,
        domains: list[str] | None = None,
        file: pathlib.Path | str | BinaryIO | None = None,
        domain_column: str | None = None,
        max_segments: int | None = None,
    ) -> AsyncJob:
        if (domains is None) == (file is None):
            raise ValueError("exactly one of domains or file is required")
        if domains is not None:
            params = {"domains": ",".join(domains), "max_segments": max_segments}
            response = await self._transport.request("GET", "/segment", params=params)
            return AsyncJob(self._transport, task_family=FAMILY_SEGMENT, task_id=response.json()["task_id"])
        assert file is not None
        return await self._segment_file(file=file, domain_column=domain_column, max_segments=max_segments)

    @api_route("POST", "/segment")
    async def _segment_file(
        self,
        *,
        file: pathlib.Path | str | BinaryIO,
        domain_column: str | None,
        max_segments: int | None,
    ) -> AsyncJob:
        params = {"domain_column": domain_column, "max_segments": max_segments}
        filename, fh, we_opened_it = open_upload(file)
        try:
            response = await self._transport.request("POST", "/segment", params=params, files={"file": (filename, fh)})
        finally:
            if we_opened_it:
                fh.close()
        return AsyncJob(self._transport, task_family=FAMILY_SEGMENT, task_id=response.json()["task_id"])
