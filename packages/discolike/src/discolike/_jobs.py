from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

import pydantic

from discolike._exceptions import JobFailedError
from discolike._exceptions import JobTimeoutError
from discolike._models import DiscolikeModel
from discolike._transport import AsyncTransport
from discolike._transport import Transport

TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
FAMILY_DISCOGEN = "discogen"
FAMILY_BULKMATCH = "bulkmatch"
FAMILY_CONTACTMATCH = "contactmatch"
FAMILY_SEGMENT = "segment"
DEFAULT_WAIT_TIMEOUT_SECONDS = 900.0
DEFAULT_POLL_INTERVAL_SECONDS = 5.0


class JobStatus(DiscolikeModel):
    status: str
    progress: int | None = None
    results: Any = None
    result: Any = None
    warnings: list[str] = pydantic.Field(default_factory=list)


class Job:
    def __init__(self, transport: Transport, *, task_family: str, task_id: str) -> None:
        self._transport = transport
        self.task_family = task_family
        self.task_id = task_id

    def status(self) -> JobStatus:
        response = self._transport.request("GET", f"/{self.task_family}/status/{self.task_id}")
        return JobStatus.model_validate(response.json())

    def cancel(self) -> None:
        self._transport.request("DELETE", f"/{self.task_family}/cancel/{self.task_id}")

    def wait(
        self,
        *,
        timeout: float = DEFAULT_WAIT_TIMEOUT_SECONDS,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
        on_poll: Callable[[JobStatus], None] | None = None,
    ) -> JobStatus:
        deadline = time.monotonic() + timeout
        while True:
            current = self.status()
            if on_poll is not None:
                on_poll(current)
            if current.status == "failed":
                raise JobFailedError(str(current.result or "task failed"), payload=current.to_dict())
            if current.status in TERMINAL_STATUSES:
                return current
            if time.monotonic() >= deadline:
                raise JobTimeoutError(
                    f"Task {self.task_id} did not finish within {timeout:.0f}s — it is still running "
                    f"server-side; call wait() again to resume or check status() later"
                )
            time.sleep(poll_interval)


class AsyncJob:
    def __init__(self, transport: AsyncTransport, *, task_family: str, task_id: str) -> None:
        self._transport = transport
        self.task_family = task_family
        self.task_id = task_id

    async def status(self) -> JobStatus:
        response = await self._transport.request("GET", f"/{self.task_family}/status/{self.task_id}")
        return JobStatus.model_validate(response.json())

    async def cancel(self) -> None:
        await self._transport.request("DELETE", f"/{self.task_family}/cancel/{self.task_id}")

    async def wait(
        self,
        *,
        timeout: float = DEFAULT_WAIT_TIMEOUT_SECONDS,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
        on_poll: Callable[[JobStatus], None] | None = None,
    ) -> JobStatus:
        deadline = time.monotonic() + timeout
        while True:
            current = await self.status()
            if on_poll is not None:
                on_poll(current)
            if current.status == "failed":
                raise JobFailedError(str(current.result or "task failed"), payload=current.to_dict())
            if current.status in TERMINAL_STATUSES:
                return current
            if time.monotonic() >= deadline:
                raise JobTimeoutError(
                    f"Task {self.task_id} did not finish within {timeout:.0f}s — it is still running "
                    f"server-side; call wait() again to resume or check status() later"
                )
            await asyncio.sleep(poll_interval)
