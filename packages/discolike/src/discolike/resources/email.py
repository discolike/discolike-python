from __future__ import annotations

from discolike._email import AsyncEmailBatch
from discolike._email import AsyncEmailJob
from discolike._email import EmailBatch
from discolike._email import EmailBatchResults
from discolike._email import EmailJob
from discolike._email import EmailJobResult
from discolike._email import EmailKind
from discolike._email import EnumerationMatch
from discolike._email import EnumerationOutput
from discolike._email import ValidationOutput
from discolike._transport import drop_none
from discolike.resources._base import AsyncAPIResource
from discolike.resources._base import SyncAPIResource
from discolike.resources._base import api_route

__all__ = [
    "AsyncEmailBatch",
    "AsyncEmailJob",
    "AsyncEmailResource",
    "EmailBatch",
    "EmailBatchResults",
    "EmailJob",
    "EmailJobResult",
    "EmailResource",
    "EnumerationMatch",
    "EnumerationOutput",
    "ValidationOutput",
]


class EmailResource(SyncAPIResource):
    @api_route("POST", "/email/find")
    def find(self, *, first_name: str, last_name: str, domain: str, known_pattern: str | None = None) -> EmailJob:
        body = {k: v for k, v in locals().items() if k != "self"}
        response = self._transport.request("POST", "/email/find", json_body=drop_none(body))
        return EmailJob(self._transport, job_id=response.json()["job_id"], kind="find")

    @api_route("POST", "/email/find/batch")
    def find_batch(self, *, contacts: list[dict[str, str]]) -> EmailBatch:
        response = self._transport.request("POST", "/email/find/batch", json_body={"requests": contacts})
        return EmailBatch(self._transport, batch_id=response.json()["batch_id"], kind="find")

    def batch(self, batch_id: str, *, kind: EmailKind) -> EmailBatch:
        return EmailBatch(self._transport, batch_id=batch_id, kind=kind)

    def job(self, job_id: str, *, kind: EmailKind = "find") -> EmailJob:
        return EmailJob(self._transport, job_id=job_id, kind=kind)


class AsyncEmailResource(AsyncAPIResource):
    @api_route("POST", "/email/find")
    async def find(
        self, *, first_name: str, last_name: str, domain: str, known_pattern: str | None = None
    ) -> AsyncEmailJob:
        body = {k: v for k, v in locals().items() if k != "self"}
        response = await self._transport.request("POST", "/email/find", json_body=drop_none(body))
        return AsyncEmailJob(self._transport, job_id=response.json()["job_id"], kind="find")

    @api_route("POST", "/email/find/batch")
    async def find_batch(self, *, contacts: list[dict[str, str]]) -> AsyncEmailBatch:
        response = await self._transport.request("POST", "/email/find/batch", json_body={"requests": contacts})
        return AsyncEmailBatch(self._transport, batch_id=response.json()["batch_id"], kind="find")

    def batch(self, batch_id: str, *, kind: EmailKind) -> AsyncEmailBatch:
        return AsyncEmailBatch(self._transport, batch_id=batch_id, kind=kind)

    def job(self, job_id: str, *, kind: EmailKind = "find") -> AsyncEmailJob:
        return AsyncEmailJob(self._transport, job_id=job_id, kind=kind)
