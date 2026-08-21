from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any
from typing import Literal

import pydantic
from typing_extensions import assert_never

from discolike._exceptions import JobFailedError
from discolike._exceptions import JobTimeoutError
from discolike._jobs import DEFAULT_POLL_INTERVAL_SECONDS
from discolike._jobs import DEFAULT_WAIT_TIMEOUT_SECONDS
from discolike._models import DiscolikeModel
from discolike._transport import AsyncTransport
from discolike._transport import Transport

EmailKind = Literal["find", "verify"]
EMAIL_TERMINAL_STATUSES = frozenset({"completed", "failed"})


class EnumerationMatch(DiscolikeModel):
    email: str | None = None
    pattern: str | None = None
    tier: int | None = None
    smtp_code: int | None = None
    valid: bool | None = None


class EnumerationOutput(DiscolikeModel):
    first_name: str | None = None
    last_name: str | None = None
    domain: str | None = None
    status: str | None = None
    result: EnumerationMatch | None = None
    is_catch_all: bool | None = None
    mx_host: str | None = None
    provider: str | None = None
    attempts: int | None = None
    duration_ms: int | None = None
    error: str | None = None


class ValidationOutput(DiscolikeModel):
    email: str | None = None
    status: str | None = None
    is_deliverable: bool | None = None
    is_catch_all: bool | None = None
    mx_host: str | None = None
    provider: str | None = None
    smtp_code: int | None = None
    attempts: int | None = None
    duration_ms: int | None = None
    error: str | None = None
    reason: str | None = None


class EmailJobResult(DiscolikeModel):
    job_id: str | None = None
    status: str | None = None
    result: EnumerationOutput | ValidationOutput | None = None
    error: str | None = None


class EmailBatchResults(DiscolikeModel):
    batch_id: str | None = None
    total: int | None = None
    completed: int | None = None
    failed: int | None = None
    results: list[EmailJobResult] = pydantic.Field(default_factory=list)


def _output_model(kind: EmailKind) -> type[EnumerationOutput] | type[ValidationOutput]:
    match kind:
        case "find":
            return EnumerationOutput
        case "verify":
            return ValidationOutput
    assert_never(kind)


def _decode_output(kind: EmailKind, raw: dict[str, Any] | None) -> EnumerationOutput | ValidationOutput | None:
    if raw is None:
        return None
    return _output_model(kind).model_validate(raw)


def _decode_job_result(kind: EmailKind, item: dict[str, Any]) -> EmailJobResult:
    server_kind = item.get("kind")
    if server_kind in ("find", "verify"):
        kind = server_kind
    return EmailJobResult(
        job_id=item.get("job_id"),
        status=item.get("status"),
        result=_decode_output(kind, item.get("result")),
        error=item.get("error"),
    )


def _decode_batch_results(kind: EmailKind, raw: dict[str, Any]) -> EmailBatchResults:
    return EmailBatchResults(
        batch_id=raw.get("batch_id"),
        total=raw.get("total"),
        completed=raw.get("completed"),
        failed=raw.get("failed"),
        results=[_decode_job_result(kind, item) for item in raw.get("results", [])],
    )


def _batch_is_done(raw: dict[str, Any]) -> bool:
    results = raw.get("results", [])
    total = raw.get("total", 0) or 0
    return len(results) >= total and all(item.get("status") in EMAIL_TERMINAL_STATUSES for item in results)


def _timeout_error(what: str, identifier: str, timeout: float) -> JobTimeoutError:
    return JobTimeoutError(
        f"{what} {identifier} did not finish within {timeout:.0f}s — it is still running "
        f"server-side; call the wait/results method again to resume or check status later"
    )


class EmailJob:
    """Handle for a single `POST /email/find` job."""

    def __init__(self, transport: Transport, *, job_id: str, kind: EmailKind = "find") -> None:
        self._transport = transport
        self.job_id = job_id
        self.kind = kind

    def status(self) -> EmailJobResult:
        response = self._transport.request("GET", f"/email/jobs/{self.job_id}")
        return _decode_job_result(self.kind, response.json())

    def wait(
        self,
        *,
        timeout: float = DEFAULT_WAIT_TIMEOUT_SECONDS,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
        on_poll: Callable[[EmailJobResult], None] | None = None,
    ) -> EnumerationOutput | ValidationOutput:
        expected = _output_model(self.kind)
        deadline = time.monotonic() + timeout
        while True:
            current = self.status()
            if on_poll is not None:
                on_poll(current)
            if current.status == "failed":
                raise JobFailedError(current.error or f"email {self.kind} job failed", payload=current.to_dict())
            if current.status in EMAIL_TERMINAL_STATUSES:
                if not isinstance(current.result, expected):
                    raise JobFailedError(f"email {self.kind} job completed without a result", payload=current.to_dict())
                return current.result
            if time.monotonic() >= deadline:
                raise _timeout_error("Email job", self.job_id, timeout)
            time.sleep(poll_interval)


class AsyncEmailJob:
    """Async handle for a single `POST /email/find` job."""

    def __init__(self, transport: AsyncTransport, *, job_id: str, kind: EmailKind = "find") -> None:
        self._transport = transport
        self.job_id = job_id
        self.kind = kind

    async def status(self) -> EmailJobResult:
        response = await self._transport.request("GET", f"/email/jobs/{self.job_id}")
        return _decode_job_result(self.kind, response.json())

    async def wait(
        self,
        *,
        timeout: float = DEFAULT_WAIT_TIMEOUT_SECONDS,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
        on_poll: Callable[[EmailJobResult], None] | None = None,
    ) -> EnumerationOutput | ValidationOutput:
        expected = _output_model(self.kind)
        deadline = time.monotonic() + timeout
        while True:
            current = await self.status()
            if on_poll is not None:
                on_poll(current)
            if current.status == "failed":
                raise JobFailedError(current.error or f"email {self.kind} job failed", payload=current.to_dict())
            if current.status in EMAIL_TERMINAL_STATUSES:
                if not isinstance(current.result, expected):
                    raise JobFailedError(f"email {self.kind} job completed without a result", payload=current.to_dict())
                return current.result
            if time.monotonic() >= deadline:
                raise _timeout_error("Email job", self.job_id, timeout)
            await asyncio.sleep(poll_interval)


class EmailBatch:
    """Handle for an email find/verify batch (`GET /email/batch/{id}/results`)."""

    def __init__(self, transport: Transport, *, batch_id: str, kind: EmailKind) -> None:
        self._transport = transport
        self.batch_id = batch_id
        self.kind = kind

    def results(
        self,
        *,
        timeout: float = DEFAULT_WAIT_TIMEOUT_SECONDS,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
        on_poll: Callable[[EmailBatchResults], None] | None = None,
    ) -> EmailBatchResults:
        deadline = time.monotonic() + timeout
        while True:
            raw = self._transport.request("GET", f"/email/batch/{self.batch_id}/results").json()
            parsed = _decode_batch_results(self.kind, raw)
            if on_poll is not None:
                on_poll(parsed)
            if _batch_is_done(raw):
                return parsed
            if time.monotonic() >= deadline:
                raise _timeout_error("Email batch", self.batch_id, timeout)
            time.sleep(poll_interval)


class AsyncEmailBatch:
    """Async handle for an email find/verify batch (`GET /email/batch/{id}/results`)."""

    def __init__(self, transport: AsyncTransport, *, batch_id: str, kind: EmailKind) -> None:
        self._transport = transport
        self.batch_id = batch_id
        self.kind = kind

    async def results(
        self,
        *,
        timeout: float = DEFAULT_WAIT_TIMEOUT_SECONDS,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
        on_poll: Callable[[EmailBatchResults], None] | None = None,
    ) -> EmailBatchResults:
        deadline = time.monotonic() + timeout
        while True:
            response = await self._transport.request("GET", f"/email/batch/{self.batch_id}/results")
            raw = response.json()
            parsed = _decode_batch_results(self.kind, raw)
            if on_poll is not None:
                on_poll(parsed)
            if _batch_is_done(raw):
                return parsed
            if time.monotonic() >= deadline:
                raise _timeout_error("Email batch", self.batch_id, timeout)
            await asyncio.sleep(poll_interval)
