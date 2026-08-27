from __future__ import annotations

import pathlib
from typing import Any
from typing import BinaryIO

from discolike._jobs import FAMILY_SEGMENT
from discolike._jobs import AsyncJob
from discolike._jobs import Job
from discolike._models import DiscolikeModel
from discolike.resources._base import AsyncAPIResource
from discolike.resources._base import SyncAPIResource
from discolike.resources._base import api_route
from discolike.resources._base import open_upload

JSON_CONTENT_TYPE = "application/json"


class AppendResult(DiscolikeModel):
    domain: str | None = None


class EnrichResource(SyncAPIResource):
    @api_route("POST", "/append")
    def append(
        self,
        *,
        file: pathlib.Path | str | BinaryIO | None = None,
        dataset: list[str] | None = None,
        domain_column: str | None = None,
        csv: bool | None = None,
        query_id: list[str] | None = None,
    ) -> list[AppendResult] | bytes:
        if file is None and query_id is None:
            raise ValueError("one of file or query_id is required")
        params = {"dataset": dataset, "domain_column": domain_column, "csv": csv, "query_id": query_id}
        if file is None:
            response = self._transport.request("POST", "/append", params=params)
        else:
            filename, fh, we_opened_it = open_upload(file)
            try:
                response = self._transport.request("POST", "/append", params=params, files={"file": (filename, fh)})
            finally:
                if we_opened_it:
                    fh.close()
        if JSON_CONTENT_TYPE in response.headers.get("Content-Type", ""):
            return [AppendResult.model_validate(item) for item in response.json()]
        return response.content

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

    @api_route("GET", "/segment")
    def segment(
        self,
        *,
        domains: list[str] | None = None,
        file: pathlib.Path | str | BinaryIO | None = None,
        domain_column: str | None = None,
        max_segments: int | None = None,
        query_id: list[str] | None = None,
    ) -> Job:
        if file is not None:
            if domains is not None or query_id is not None:
                raise ValueError("file cannot be combined with domains or query_id")
            return self._segment_file(file=file, domain_column=domain_column, max_segments=max_segments)
        if domains is None and query_id is None:
            raise ValueError("one of domains, query_id, or file is required")
        if domain_column is not None:
            raise ValueError("domain_column only applies to file uploads")
        params: dict[str, Any] = {"max_segments": max_segments}
        if domains is not None:
            params["domains"] = ",".join(domains)
        if query_id is not None:
            params["query_id"] = ",".join(query_id)
        response = self._transport.request("GET", "/segment", params=params)
        return Job(self._transport, task_family=FAMILY_SEGMENT, task_id=response.json()["task_id"])


class AsyncEnrichResource(AsyncAPIResource):
    @api_route("POST", "/append")
    async def append(
        self,
        *,
        file: pathlib.Path | str | BinaryIO | None = None,
        dataset: list[str] | None = None,
        domain_column: str | None = None,
        csv: bool | None = None,
        query_id: list[str] | None = None,
    ) -> list[AppendResult] | bytes:
        if file is None and query_id is None:
            raise ValueError("one of file or query_id is required")
        params = {"dataset": dataset, "domain_column": domain_column, "csv": csv, "query_id": query_id}
        if file is None:
            response = await self._transport.request("POST", "/append", params=params)
        else:
            filename, fh, we_opened_it = open_upload(file)
            try:
                response = await self._transport.request(
                    "POST", "/append", params=params, files={"file": (filename, fh)}
                )
            finally:
                if we_opened_it:
                    fh.close()
        if JSON_CONTENT_TYPE in response.headers.get("Content-Type", ""):
            return [AppendResult.model_validate(item) for item in response.json()]
        return response.content

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

    @api_route("GET", "/segment")
    async def segment(
        self,
        *,
        domains: list[str] | None = None,
        file: pathlib.Path | str | BinaryIO | None = None,
        domain_column: str | None = None,
        max_segments: int | None = None,
        query_id: list[str] | None = None,
    ) -> AsyncJob:
        if file is not None:
            if domains is not None or query_id is not None:
                raise ValueError("file cannot be combined with domains or query_id")
            return await self._segment_file(file=file, domain_column=domain_column, max_segments=max_segments)
        if domains is None and query_id is None:
            raise ValueError("one of domains, query_id, or file is required")
        if domain_column is not None:
            raise ValueError("domain_column only applies to file uploads")
        params: dict[str, Any] = {"max_segments": max_segments}
        if domains is not None:
            params["domains"] = ",".join(domains)
        if query_id is not None:
            params["query_id"] = ",".join(query_id)
        response = await self._transport.request("GET", "/segment", params=params)
        return AsyncJob(self._transport, task_family=FAMILY_SEGMENT, task_id=response.json()["task_id"])
