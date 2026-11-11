from __future__ import annotations

import asyncio
import builtins
import time
from datetime import datetime
from decimal import Decimal
from typing import Any
from typing import Literal
from uuid import UUID

from pydantic import Field

from discolike._exceptions import JobTimeoutError
from discolike._models import DiscolikeModel
from discolike.requests import ContactsRunEventsParams
from discolike.requests import ContactsRunGetParams
from discolike.requests import ContactsRunListParams
from discolike.requests import ContactsRunRequest
from discolike.requests import ContinueRunRequest
from discolike.requests import TitlePreviewRequest
from discolike.resources._base import AsyncAPIResource
from discolike.resources._base import SyncAPIResource
from discolike.resources._base import api_route
from discolike.resources.prospecting import _deadline

RUN_PATH = "/contacts/run"
TERMINAL_STATUSES = frozenset({"done", "failed", "cancelled"})
ROWS_PAGE_SIZE = 1000
DEFAULT_MAX_WAIT_SECONDS = 3600.0
DEFAULT_POLL_INTERVAL_SECONDS = 5.0

ContactsRunStatus = Literal["ready", "running", "waiting", "done", "failed", "cancelled"] | str
ContactsRunStepName = Literal["find_contacts", "find_missing", "review", "find_emails", "discover", "validate"] | str
ContactsRunStepStatus = Literal["pending", "running", "done", "failed", "skipped", "cancelled"] | str


class ContactsRunStep(DiscolikeModel):
    status: ContactsRunStepStatus
    error: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    estimate_usd: Decimal | None = None
    charged_usd: Decimal = Decimal(0)


class ContactsRunRow(DiscolikeModel):
    row_key: str
    persona_id: int | None = None
    domain: str
    name: str | None = None
    title: str | None = None
    linkedin_url: str | None = None
    seniority: str | None = None
    department: str | None = None
    debug_only: bool | None = None
    reason: str | None = None
    company_score: float | None = None
    p_fit: float | None = None
    fit_label: str | None = None
    floor: bool = False
    not_fit: bool = False
    email: str | None = None
    email_status: Literal["Validated", "Validated (catch-all resolved)"] | str | None = None
    email_state: Literal["checking", "queued", "skipped"] | str | None = None


class RunCompanyResponse(DiscolikeModel):
    company: dict[str, Any] = Field(default_factory=dict)
    domain: str
    status: Literal["pending", "finding_people", "finding_emails", "validated", "skipped", "cancelled", "failed"] | str
    people_reviewed: int = 0
    mailboxes_checked: int = 0
    validated_contacts: int = 0
    contacts: list[ContactsRunRow] = Field(default_factory=list)


class ContactsRunSummary(DiscolikeModel):
    skipped_no_mx: int | None = None
    stop_reason: Literal["low_delivery_yield", "source_exhausted"] | str | None = None
    companies_delivered: int = 0
    validated_contacts: int = 0
    spent_usd: Decimal = Decimal(0)


class ValidatedRunTitle(DiscolikeModel):
    title: str | None = None
    status: Literal["Validated", "Validated (catch-all resolved)"] | str


class ContactsRunEvent(DiscolikeModel):
    company_name: str | None = None
    seq: int
    domain: str
    created_at: datetime
    kind: Literal["progress", "company_skipped"] | str
    status: str
    people_reviewed: int = 0
    titles_considered: list[str] = Field(default_factory=list)
    mailboxes_checked: int = 0
    validated_titles: list[ValidatedRunTitle] = Field(default_factory=list)


class ContactsRunEventsResponse(DiscolikeModel):
    events: list[ContactsRunEvent] = Field(default_factory=list)
    next_cursor: int = 0


class AppliedCompanyFilters(DiscolikeModel):
    """Effective company filters returned by the server, without request validation limits."""

    filter_industry: list[str] | None = None
    negate_filter_industry: list[str] | None = None
    filter_country: list[str] | None = None
    negate_filter_country: list[str] | None = None
    filter_state: list[str] | None = None
    negate_filter_state: list[str] | None = None
    employee_range: str | None = None
    revenue_range: str | None = None
    sub_industry: list[str] | None = None


class ContactsRun(DiscolikeModel):
    applied_company_filters: AppliedCompanyFilters | None = None
    contacts_total: int = 0
    progress: dict[str, int] = Field(default_factory=dict)
    error: str | None = None
    companies: list[RunCompanyResponse] = Field(default_factory=list)
    companies_total: int = 0
    summary: ContactsRunSummary | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    id: str
    kind: Literal["contacts", "companies"] | str
    status: ContactsRunStatus
    current_step: ContactsRunStepName | None = None
    generation: int
    steps: dict[str, ContactsRunStep] = Field(default_factory=dict)
    total_estimate_usd: Decimal | None = None
    total_charged_usd: Decimal = Decimal(0)
    created_at: datetime
    updated_at: datetime
    expires_at: datetime


class TitlePreviewTitle(DiscolikeModel):
    title: str
    role: float
    count: int


class TitlePreview(DiscolikeModel):
    searched: list[str] = Field(default_factory=list)
    titles: list[TitlePreviewTitle] = Field(default_factory=list)


def _path(run_id: str | UUID) -> str:
    return f"{RUN_PATH}/{UUID(str(run_id))}"


class ContactsRunResource(SyncAPIResource):
    @api_route("POST", RUN_PATH, openapi=False)
    def create(self, request: ContactsRunRequest) -> ContactsRun:
        """Start automatic contact discovery and validated delivery, optionally capped by email_cap_usd."""
        response = self._transport.request("POST", RUN_PATH, json_body=request.to_wire())
        return ContactsRun.model_validate(response.json())

    @api_route("GET", RUN_PATH, openapi=False)
    def list(self, params: ContactsRunListParams | None = None) -> builtins.list[ContactsRun]:
        """List your runs, newest first (default 20, maximum 100); page with `before`, the last run's created_at."""
        response = self._transport.request("GET", RUN_PATH, params=params.to_wire() if params else None)
        return [ContactsRun.model_validate(item) for item in response.json()]

    @api_route("GET", RUN_PATH + "/{run_id}", openapi=False)
    def get(self, run_id: str | UUID, params: ContactsRunGetParams | None = None) -> ContactsRun:
        response = self._transport.request("GET", _path(run_id), params=params.to_wire() if params else None)
        return ContactsRun.model_validate(response.json())

    def rows(self, run_id: str | UUID, *, page_size: int = ROWS_PAGE_SIZE) -> builtins.list[ContactsRunRow]:
        """Every row of the run, fetched page by page."""
        rows: builtins.list[ContactsRunRow] = []
        offset = 0
        while True:
            run = self.get(run_id, ContactsRunGetParams(rows_offset=offset, rows_limit=page_size))
            rows.extend(contact for company in run.companies for contact in company.contacts)
            offset += len(run.companies)
            if not run.companies or offset >= run.companies_total:
                return rows

    @api_route("POST", RUN_PATH + "/{run_id}/continue", openapi=False)
    def continue_(self, run_id: str | UUID, request: ContinueRunRequest) -> ContactsRun:
        """Advance a companies run; contacts runs proceed automatically and return 409 here."""
        response = self._transport.request("POST", _path(run_id) + "/continue", json_body=request.to_wire())
        return ContactsRun.model_validate(response.json())

    @api_route("GET", RUN_PATH + "/{run_id}/events", openapi=False)
    def events(self, run_id: str | UUID, params: ContactsRunEventsParams | None = None) -> ContactsRunEventsResponse:
        response = self._transport.request(
            "GET", _path(run_id) + "/events", params=params.to_wire() if params else None
        )
        return ContactsRunEventsResponse.model_validate(response.json())

    @api_route("POST", RUN_PATH + "/{run_id}/cancel", openapi=False)
    def cancel(self, run_id: str | UUID) -> ContactsRun:
        response = self._transport.request("POST", _path(run_id) + "/cancel")
        return ContactsRun.model_validate(response.json())

    @api_route("POST", RUN_PATH + "/title-preview", openapi=False)
    def title_preview(self, request: TitlePreviewRequest) -> TitlePreview:
        """The titles a people spec would match, with each one's role score and contact count."""
        response = self._transport.request("POST", RUN_PATH + "/title-preview", json_body=request.to_wire())
        return TitlePreview.model_validate(response.json())

    def wait(
        self,
        run_id: str | UUID,
        *,
        max_wait: float = DEFAULT_MAX_WAIT_SECONDS,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> ContactsRun:
        """Poll until done, failed or cancelled. Timeout stops local polling only."""
        deadline = _deadline(max_wait, poll_interval)
        while True:
            run = self.get(run_id)
            if run.status in TERMINAL_STATUSES:
                return run
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise JobTimeoutError("Timed out waiting for the contacts run; it continues on the server")
            time.sleep(min(poll_interval, remaining))


class AsyncContactsRunResource(AsyncAPIResource):
    @api_route("POST", RUN_PATH, openapi=False)
    async def create(self, request: ContactsRunRequest) -> ContactsRun:
        response = await self._transport.request("POST", RUN_PATH, json_body=request.to_wire())
        return ContactsRun.model_validate(response.json())

    @api_route("GET", RUN_PATH, openapi=False)
    async def list(self, params: ContactsRunListParams | None = None) -> builtins.list[ContactsRun]:
        response = await self._transport.request("GET", RUN_PATH, params=params.to_wire() if params else None)
        return [ContactsRun.model_validate(item) for item in response.json()]

    @api_route("GET", RUN_PATH + "/{run_id}", openapi=False)
    async def get(self, run_id: str | UUID, params: ContactsRunGetParams | None = None) -> ContactsRun:
        response = await self._transport.request("GET", _path(run_id), params=params.to_wire() if params else None)
        return ContactsRun.model_validate(response.json())

    async def rows(self, run_id: str | UUID, *, page_size: int = ROWS_PAGE_SIZE) -> builtins.list[ContactsRunRow]:
        rows: builtins.list[ContactsRunRow] = []
        offset = 0
        while True:
            run = await self.get(run_id, ContactsRunGetParams(rows_offset=offset, rows_limit=page_size))
            rows.extend(contact for company in run.companies for contact in company.contacts)
            offset += len(run.companies)
            if not run.companies or offset >= run.companies_total:
                return rows

    @api_route("POST", RUN_PATH + "/{run_id}/continue", openapi=False)
    async def continue_(self, run_id: str | UUID, request: ContinueRunRequest) -> ContactsRun:
        response = await self._transport.request("POST", _path(run_id) + "/continue", json_body=request.to_wire())
        return ContactsRun.model_validate(response.json())

    @api_route("GET", RUN_PATH + "/{run_id}/events", openapi=False)
    async def events(
        self, run_id: str | UUID, params: ContactsRunEventsParams | None = None
    ) -> ContactsRunEventsResponse:
        response = await self._transport.request(
            "GET", _path(run_id) + "/events", params=params.to_wire() if params else None
        )
        return ContactsRunEventsResponse.model_validate(response.json())

    @api_route("POST", RUN_PATH + "/{run_id}/cancel", openapi=False)
    async def cancel(self, run_id: str | UUID) -> ContactsRun:
        response = await self._transport.request("POST", _path(run_id) + "/cancel")
        return ContactsRun.model_validate(response.json())

    @api_route("POST", RUN_PATH + "/title-preview", openapi=False)
    async def title_preview(self, request: TitlePreviewRequest) -> TitlePreview:
        response = await self._transport.request("POST", RUN_PATH + "/title-preview", json_body=request.to_wire())
        return TitlePreview.model_validate(response.json())

    async def wait(
        self,
        run_id: str | UUID,
        *,
        max_wait: float = DEFAULT_MAX_WAIT_SECONDS,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> ContactsRun:
        deadline = _deadline(max_wait, poll_interval)
        while True:
            run = await self.get(run_id)
            if run.status in TERMINAL_STATUSES:
                return run
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise JobTimeoutError("Timed out waiting for the contacts run; it continues on the server")
            await asyncio.sleep(min(poll_interval, remaining))
