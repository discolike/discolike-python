from __future__ import annotations

import asyncio
import builtins
import math
import time
from datetime import datetime
from typing import Any
from typing import Literal
from uuid import UUID

from pydantic import Field

from discolike._exceptions import JobTimeoutError
from discolike._models import DiscolikeModel
from discolike.requests import ProspectingApproveRequest
from discolike.requests import ProspectingBrief
from discolike.requests import ProspectingGetParams
from discolike.requests import ProspectingListParams
from discolike.requests import ProspectingMessageRequest
from discolike.resources._base import AsyncAPIResource
from discolike.resources._base import SyncAPIResource
from discolike.resources._base import api_route

WAIT_STATUSES = frozenset({"proposed", "completed", "needs_input", "failed", "cancelled"})
CHECKPOINT_STOP_REASONS = frozenset({"pilot", "tail_quality", "short", "target_reached"})
ProspectingStatus = Literal[
    "drafting", "proposed", "queued", "running", "needs_input", "completed", "failed", "cancelled"
]
ProspectingStage = Literal["plan", "discover", "validate", "contacts", "generate", "verify", "segment"]


class ProspectingPlan(DiscolikeModel):
    company_queries: list[dict[str, Any]] = Field(default_factory=list)
    contact_filters: dict[str, Any] = Field(default_factory=dict)
    company_criteria: str
    persona_criteria: str
    issues: list[str] = Field(default_factory=list)


class ProspectingEvent(DiscolikeModel):
    seq: int
    created_at: datetime
    stage: str | None = None
    kind: Literal["queued", "decision", "started", "progress", "result", "stopped", "warning"]
    message: str
    data: dict[str, Any] | None = None


class ProspectingMessage(DiscolikeModel):
    seq: int
    created_at: datetime
    role: Literal["user", "agent"]
    kind: Literal["text", "plan", "milestone", "question", "ack", "error"]
    content: str
    data: dict[str, Any] | None = None


class ProspectingInFlight(DiscolikeModel):
    stage: ProspectingStage
    items: int
    plan_version: int
    state: Literal["dispatching", "running"]
    started_at: datetime


class ProspectingRunSummary(DiscolikeModel):
    run_id: UUID
    status: ProspectingStatus
    title: str | None = None
    stop_reason: str | None = None
    stage: str | None = None
    brief: str = Field(max_length=200)
    target_companies: int
    contacts_per_company: int
    qualified_companies: int = 0
    accepted_contacts: int = 0
    created_at: datetime
    updated_at: datetime


class ProspectingRun(DiscolikeModel):
    run_id: UUID
    status: ProspectingStatus
    stop_reason: str | None = None
    stage: str | None = None
    phase: str | None = None
    created_at: datetime
    updated_at: datetime
    brief: ProspectingBrief
    target_companies: int
    contacts_per_company: int
    plan: ProspectingPlan | None = None
    last_decision: dict[str, Any] | None = None
    events: list[ProspectingEvent] = Field(default_factory=list)
    next_event_seq: int = 0
    waiting_for_worker: bool = False
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
    title: str | None = None
    plan_version: int = 1
    approved_plan_version: int | None = None
    saved_query_id: UUID | None = None
    saved_query_ids: list[UUID] = Field(
        default_factory=list,
        description="Every saved contact list for this run, in order. Large results are split across several "
        "lists; the first is saved_query_id. Parts are final once the run reaches a terminal status.",
    )
    messages: list[ProspectingMessage] = Field(default_factory=list)
    next_message_seq: int = 0
    in_flight: list[ProspectingInFlight] = Field(default_factory=list)
    fit_companies: int = 0
    emails_found: int = 0
    reply_pending: bool = False
    chat_closed: bool = Field(
        default=False,
        description="The chat was closed for off-topic use: every new message gets the same fixed reply. "
        "An approved run keeps working and its saved lists still fill.",
    )
    pilot_sample: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Checked companies (domain, name, company_fit, reason) when stop_reason is pilot_failed.",
    )


def _key(value: str) -> str:
    if not value.strip() or len(value) > 128:
        raise ValueError("idempotency_key must contain 1-128 characters")
    if not value.isascii() or not value.isprintable():
        raise ValueError("idempotency_key must be printable ASCII with no control characters")
    return value


def _path(run_id: str | UUID) -> str:
    return f"/prospecting/runs/{UUID(str(run_id))}"


def _deadline(timeout: float, poll_interval: float) -> float:
    if not math.isfinite(timeout) or timeout <= 0 or not math.isfinite(poll_interval) or poll_interval < 5:
        raise ValueError("timeout must be finite and positive; poll_interval must be finite and at least 5 seconds")
    return time.monotonic() + timeout


class ProspectingResource(SyncAPIResource):
    @api_route("GET", "/prospecting/runs")
    def list(self, params: ProspectingListParams | None = None) -> builtins.list[ProspectingRunSummary]:
        """List recent organization runs, newest first; default 20, maximum 50.

        Pass `before` (a run ID) to page past a full page of results.
        """
        response = self._transport.request("GET", "/prospecting/runs", params=params.to_wire() if params else None)
        return [ProspectingRunSummary.model_validate(row) for row in response.json()]

    @api_route("POST", "/prospecting/runs/{run_id}/approve")
    def approve(self, run_id: str | UUID, request: ProspectingApproveRequest) -> ProspectingRun:
        """Approve the reviewed plan version; repeating the same approval is safe.

        `checkpoints` on the request overrides the brief's mode; None keeps it.
        """
        response = self._transport.request("POST", _path(run_id) + "/approve", json_body=request.to_wire())
        return ProspectingRun.model_validate(response.json())

    @api_route("POST", "/prospecting/runs/{run_id}/messages")
    def message(
        self, run_id: str | UUID, request: ProspectingMessageRequest, *, idempotency_key: str
    ) -> ProspectingMessage:
        """Send a chat message; poll get() with ProspectingGetParams(messages_after=...) for the agent's reply."""
        response = self._transport.request(
            "POST",
            _path(run_id) + "/messages",
            json_body=request.to_wire(),
            headers={"Idempotency-Key": _key(idempotency_key)},
        )
        return ProspectingMessage.model_validate(response.json())

    @api_route("POST", "/prospecting/runs")
    def start(self, request: ProspectingBrief, *, idempotency_key: str) -> ProspectingRun:
        """Draft a plan for approval; retain the key when retrying this submission."""
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
        """Return the first page when approval, input, or a terminal outcome is ready.

        A proposed run needs approve() with its plan_version before research starts.
        Inspect status and stop_reason; completed does not guarantee the target was met.
        A run in checkpoints="ask" mode returns needs_input with a stop_reason in
        CHECKPOINT_STOP_REASONS; answer the latest kind="question" message through message(),
        then wait again.
        Timeout stops local polling only. Fetch subsequent pages with get().
        """
        deadline = _deadline(timeout, poll_interval)
        while True:
            run = self.get(run_id)
            if run.status in WAIT_STATUSES:
                return run
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise JobTimeoutError("Timed out waiting for prospecting; the run continues on the server")
            time.sleep(min(poll_interval, remaining))


class AsyncProspectingResource(AsyncAPIResource):
    @api_route("GET", "/prospecting/runs")
    async def list(self, params: ProspectingListParams | None = None) -> builtins.list[ProspectingRunSummary]:
        """List recent organization runs, newest first; default 20, maximum 50.

        Pass `before` (a run ID) to page past a full page of results.
        """
        response = await self._transport.request(
            "GET", "/prospecting/runs", params=params.to_wire() if params else None
        )
        return [ProspectingRunSummary.model_validate(row) for row in response.json()]

    @api_route("POST", "/prospecting/runs/{run_id}/approve")
    async def approve(self, run_id: str | UUID, request: ProspectingApproveRequest) -> ProspectingRun:
        """Approve the reviewed plan version; repeating the same approval is safe.

        `checkpoints` on the request overrides the brief's mode; None keeps it.
        """
        response = await self._transport.request("POST", _path(run_id) + "/approve", json_body=request.to_wire())
        return ProspectingRun.model_validate(response.json())

    @api_route("POST", "/prospecting/runs/{run_id}/messages")
    async def message(
        self, run_id: str | UUID, request: ProspectingMessageRequest, *, idempotency_key: str
    ) -> ProspectingMessage:
        """Send a chat message; poll get() with ProspectingGetParams(messages_after=...) for the agent's reply."""
        response = await self._transport.request(
            "POST",
            _path(run_id) + "/messages",
            json_body=request.to_wire(),
            headers={"Idempotency-Key": _key(idempotency_key)},
        )
        return ProspectingMessage.model_validate(response.json())

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
        """Return the first page on proposed/needs_input/completed/failed/cancelled; inspect status.

        A needs_input run with a stop_reason in CHECKPOINT_STOP_REASONS waits for an answer via message().
        """
        deadline = _deadline(timeout, poll_interval)
        while True:
            run = await self.get(run_id)
            if run.status in WAIT_STATUSES:
                return run
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise JobTimeoutError("Timed out waiting for prospecting; the run continues on the server")
            await asyncio.sleep(min(poll_interval, remaining))
