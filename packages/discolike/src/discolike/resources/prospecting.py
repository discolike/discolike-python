from __future__ import annotations

import asyncio
import math
import time
from typing import Any
from typing import Literal
from uuid import UUID

from pydantic import Field

from discolike._exceptions import JobTimeoutError
from discolike._models import DiscolikeModel
from discolike.requests import ProspectingBrief
from discolike.requests import ProspectingGetParams
from discolike.resources._base import AsyncAPIResource
from discolike.resources._base import SyncAPIResource
from discolike.resources._base import api_route

TERMINAL_STATUSES = frozenset({"completed", "needs_input", "failed", "cancelled"})


class ProspectingPlan(DiscolikeModel):
    company_queries: list[dict[str, Any]] = Field(default_factory=list)
    contact_filters: dict[str, Any] = Field(default_factory=dict)
    company_criteria: str
    persona_criteria: str
    issues: list[str] = Field(default_factory=list)


class ProspectingRun(DiscolikeModel):
    run_id: UUID
    status: Literal["queued", "running", "needs_input", "completed", "failed", "cancelled"]
    stop_reason: str | None = None
    stage: str | None = None
    plan: ProspectingPlan | None = None
    companies: list[dict[str, Any]] = Field(default_factory=list)
    contacts: list[dict[str, Any]] = Field(default_factory=list)
    total_companies: int = 0
    total_contacts: int = 0
    qualified_companies: int = 0
    accepted_contacts: int = 0
    offset: int = 0
    limit: int = 100
    actions_used: int = 0
    max_actions: int
    error: str | None = None


def _key(value: str) -> str:
    if not value.strip() or len(value) > 128:
        raise ValueError("idempotency_key must contain 1-128 characters")
    return value


def _path(run_id: str | UUID) -> str:
    return f"/prospecting/runs/{UUID(str(run_id))}"


def _deadline(timeout: float, poll_interval: float) -> float:
    if not math.isfinite(timeout) or timeout <= 0 or not math.isfinite(poll_interval) or poll_interval < 5:
        raise ValueError("timeout must be finite and positive; poll_interval must be finite and at least 5 seconds")
    return time.monotonic() + timeout


class ProspectingResource(SyncAPIResource):
    @api_route("POST", "/prospecting/runs")
    def start(self, request: ProspectingBrief, *, idempotency_key: str) -> ProspectingRun:
        """Start a managed run; retain the key when retrying this submission."""
        response = self._transport.request(
            "POST", "/prospecting/runs", json_body=request.to_wire(), headers={"Idempotency-Key": _key(idempotency_key)}
        )
        return ProspectingRun.model_validate(response.json())

    @api_route("GET", "/prospecting/runs/{run_id}")
    def get(self, run_id: str | UUID, params: ProspectingGetParams | None = None) -> ProspectingRun:
        response = self._transport.request("GET", _path(run_id), params=params.to_wire() if params else None)
        return ProspectingRun.model_validate(response.json())

    @api_route("DELETE", "/prospecting/runs/{run_id}")
    def cancel(self, run_id: str | UUID) -> ProspectingRun:
        response = self._transport.request("DELETE", _path(run_id))
        return ProspectingRun.model_validate(response.json())

    def wait(self, run_id: str | UUID, *, timeout: float = 3600, poll_interval: float = 5) -> ProspectingRun:
        """Return the first result page at any terminal status, preserving partial results.

        Inspect status and stop_reason; completed does not guarantee the target was met.
        Timeout stops local polling only. Fetch subsequent pages with get().
        """
        deadline = _deadline(timeout, poll_interval)
        while True:
            run = self.get(run_id)
            if run.status in TERMINAL_STATUSES:
                return run
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise JobTimeoutError("Timed out waiting for prospecting; the run continues on the server")
            time.sleep(min(poll_interval, remaining))


class AsyncProspectingResource(AsyncAPIResource):
    @api_route("POST", "/prospecting/runs")
    async def start(self, request: ProspectingBrief, *, idempotency_key: str) -> ProspectingRun:
        response = await self._transport.request(
            "POST", "/prospecting/runs", json_body=request.to_wire(), headers={"Idempotency-Key": _key(idempotency_key)}
        )
        return ProspectingRun.model_validate(response.json())

    @api_route("GET", "/prospecting/runs/{run_id}")
    async def get(self, run_id: str | UUID, params: ProspectingGetParams | None = None) -> ProspectingRun:
        response = await self._transport.request("GET", _path(run_id), params=params.to_wire() if params else None)
        return ProspectingRun.model_validate(response.json())

    @api_route("DELETE", "/prospecting/runs/{run_id}")
    async def cancel(self, run_id: str | UUID) -> ProspectingRun:
        response = await self._transport.request("DELETE", _path(run_id))
        return ProspectingRun.model_validate(response.json())

    async def wait(self, run_id: str | UUID, *, timeout: float = 3600, poll_interval: float = 5) -> ProspectingRun:
        """Return the first page on completed/needs_input/failed/cancelled; inspect stop_reason."""
        deadline = _deadline(timeout, poll_interval)
        while True:
            run = await self.get(run_id)
            if run.status in TERMINAL_STATUSES:
                return run
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise JobTimeoutError("Timed out waiting for prospecting; the run continues on the server")
            await asyncio.sleep(min(poll_interval, remaining))
