from __future__ import annotations

import pathlib
from typing import BinaryIO

from discolike._jobs import FAMILY_BULKMATCH
from discolike._jobs import AsyncJob
from discolike._jobs import Job
from discolike._models import DiscolikeModel
from discolike.resources._base import AsyncAPIResource
from discolike.resources._base import SyncAPIResource
from discolike.resources._base import api_route
from discolike.resources._base import open_upload


class MatchResponse(DiscolikeModel):
    pass


class MatchResource(SyncAPIResource):
    @api_route("GET", "/match")
    def company(
        self,
        *,
        name: str,
        phone: str | None = None,
        city: str | None = None,
        state: str | None = None,
        country: str | None = None,
        zip_code: str | None = None,
        strict: bool | None = None,
        local_mode: bool | None = None,
    ) -> MatchResponse:
        params = {k: v for k, v in locals().items() if k != "self"}
        return MatchResponse.model_validate(self._transport.request("GET", "/match", params=params).json())

    @api_route("POST", "/bulkmatch")
    def bulk(
        self,
        *,
        file: pathlib.Path | str | BinaryIO,
        name_column: str,
        phone_column: str | None = None,
        city_column: str | None = None,
        state_column: str | None = None,
        country_column: str | None = None,
        zip_code_column: str | None = None,
        strict: bool | None = None,
        local_mode: bool | None = None,
    ) -> Job:
        params = {
            "name_column": name_column,
            "phone_column": phone_column,
            "city_column": city_column,
            "state_column": state_column,
            "country_column": country_column,
            "zip_code_column": zip_code_column,
            "strict": strict,
            "local_mode": local_mode,
        }
        filename, fh, we_opened_it = open_upload(file)
        try:
            response = self._transport.request("POST", "/bulkmatch", params=params, files={"file": (filename, fh)})
        finally:
            if we_opened_it:
                fh.close()
        return Job(self._transport, task_family=FAMILY_BULKMATCH, task_id=response.json()["task_id"])


class AsyncMatchResource(AsyncAPIResource):
    @api_route("GET", "/match")
    async def company(
        self,
        *,
        name: str,
        phone: str | None = None,
        city: str | None = None,
        state: str | None = None,
        country: str | None = None,
        zip_code: str | None = None,
        strict: bool | None = None,
        local_mode: bool | None = None,
    ) -> MatchResponse:
        params = {k: v for k, v in locals().items() if k != "self"}
        return MatchResponse.model_validate((await self._transport.request("GET", "/match", params=params)).json())

    @api_route("POST", "/bulkmatch")
    async def bulk(
        self,
        *,
        file: pathlib.Path | str | BinaryIO,
        name_column: str,
        phone_column: str | None = None,
        city_column: str | None = None,
        state_column: str | None = None,
        country_column: str | None = None,
        zip_code_column: str | None = None,
        strict: bool | None = None,
        local_mode: bool | None = None,
    ) -> AsyncJob:
        params = {
            "name_column": name_column,
            "phone_column": phone_column,
            "city_column": city_column,
            "state_column": state_column,
            "country_column": country_column,
            "zip_code_column": zip_code_column,
            "strict": strict,
            "local_mode": local_mode,
        }
        filename, fh, we_opened_it = open_upload(file)
        try:
            response = await self._transport.request(
                "POST", "/bulkmatch", params=params, files={"file": (filename, fh)}
            )
        finally:
            if we_opened_it:
                fh.close()
        return AsyncJob(self._transport, task_family=FAMILY_BULKMATCH, task_id=response.json()["task_id"])
