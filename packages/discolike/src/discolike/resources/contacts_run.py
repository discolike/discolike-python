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
CONTACTS_KIND = "contacts"
CONTACTS_STEP_ORDER = ("find_contacts", "find_missing", "review", "find_emails")
FIND_EMAILS_STEP = "find_emails"
EMAIL_CAP_INPUT_KEY = "email_cap_usd"
FAILED_STEP_STATUS = "failed"
TERMINAL_STATUSES = frozenset({"done", "failed", "cancelled"})
PAUSED_STATUSES = frozenset({"ready", "waiting"})
ROWS_PAGE_SIZE = 1000
DEFAULT_MAX_WAIT_SECONDS = 3600.0
DEFAULT_POLL_INTERVAL_SECONDS = 5.0

ContactsRunStatus = Literal["ready", "running", "waiting", "done", "failed", "cancelled"] | str
ContactsRunStepName = Literal["find_contacts", "find_missing", "review", "find_emails", "discover", "validate"] | str
ContactsRunStepStatus = Literal["pending", "running", "done", "failed", "skipped", "cancelled"] | str


class ContactsRunStep(DiscolikeModel):
    status: ContactsRunStepStatus
    counts: dict[str, int] = Field(default_factory=dict)
    estimate_usd: Decimal | None = None
    charged_usd: Decimal = Decimal(0)
    child_task_id: str | None = None
    state: dict[str, Any] = Field(default_factory=dict)


class ContactsRunRow(DiscolikeModel):
    row_key: str
    persona_id: int | None = None
    domain: str
    name: str | None = None
    title: str | None = None
    linkedin_url: str | None = None
    seniority: str | None = None
    department: str | None = None
    source: Literal["database", "web_search"] | str
    company_score: float | None = None
    p_fit: float | None = None
    fit_label: str | None = None
    floor: bool = False
    not_fit: bool = False
    email: str | None = None
    email_status: str | None = None
    company: dict[str, Any] = Field(default_factory=dict)


class ContactsRun(DiscolikeModel):
    input: dict[str, Any] = Field(default_factory=dict)
    id: str
    kind: Literal["contacts", "companies"] | str
    status: ContactsRunStatus
    current_step: ContactsRunStepName
    generation: int
    steps: dict[str, ContactsRunStep] = Field(default_factory=dict)
    total_estimate_usd: Decimal | None = None
    total_charged_usd: Decimal = Decimal(0)
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    rows: list[ContactsRunRow] = Field(default_factory=list)
    rows_total: int = 0


class TitlePreviewTitle(DiscolikeModel):
    title: str
    role: float
    count: int


class TitlePreview(DiscolikeModel):
    titles: list[TitlePreviewTitle] = Field(default_factory=list)


def _path(run_id: str | UUID) -> str:
    return f"{RUN_PATH}/{UUID(str(run_id))}"


def _follow_request(run: ContactsRun, *, email_cap_usd: Decimal | float | None) -> ContinueRunRequest | None:
    if run.kind != CONTACTS_KIND or run.current_step not in CONTACTS_STEP_ORDER:
        return None
    if run.status == "ready":
        return ContinueRunRequest(generation=run.generation)
    current = run.steps.get(run.current_step)
    if current is not None and current.status == FAILED_STEP_STATUS:
        return None
    index = CONTACTS_STEP_ORDER.index(run.current_step) + 1
    if index >= len(CONTACTS_STEP_ORDER):
        return None
    if CONTACTS_STEP_ORDER[index] != FIND_EMAILS_STEP or (
        email_cap_usd is None and run.input.get(EMAIL_CAP_INPUT_KEY) is not None
    ):
        return ContinueRunRequest(generation=run.generation)
    if email_cap_usd is None:
        return None
    return ContinueRunRequest(generation=run.generation, email_cap_usd=Decimal(str(email_cap_usd)))


class ContactsRunResource(SyncAPIResource):
    @api_route("POST", RUN_PATH, openapi=False)
    def create(self, request: ContactsRunRequest) -> ContactsRun:
        """Start a contacts run; it runs find_contacts -> find_missing -> review -> find_emails.

        With mode="step_by_step" (the default) the run pauses with status "waiting" after each step;
        call continue_() to move on, or wait(follow=True). An optional email_cap_usd, given here or on
        the continue that enters find_emails, caps what find_emails spends; without one it runs until
        the account balance runs out.
        """
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
        while True:
            run = self.get(run_id, ContactsRunGetParams(rows_offset=len(rows), rows_limit=page_size))
            rows.extend(run.rows)
            if not run.rows or len(rows) >= run.rows_total:
                return rows

    @api_route("POST", RUN_PATH + "/{run_id}/continue", openapi=False)
    def continue_(self, run_id: str | UUID, request: ContinueRunRequest) -> ContactsRun:
        """Start the next step, or redo the current one with redo=True.

        Pass the run's current generation. ValidationError with status_code 409 means the run changed
        since or its current step failed and needs redo=True; a 410
        (DiscolikeError) means the run sat idle past its expires_at.
        """
        response = self._transport.request("POST", _path(run_id) + "/continue", json_body=request.to_wire())
        return ContactsRun.model_validate(response.json())

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
        follow: bool = False,
        email_cap_usd: Decimal | float | None = None,
        max_wait: float = DEFAULT_MAX_WAIT_SECONDS,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> ContactsRun:
        """Poll until the run finishes or pauses (status "ready" or "waiting").

        With follow=True a paused run is continued step by step instead, stopping at a failed step
        (continue it with redo=True) and before find_emails unless the run was created with an
        email_cap_usd or one is given here, which is sent on the continue that enters find_emails.
        Timeout stops local polling only.
        """
        deadline = _deadline(max_wait, poll_interval)
        while True:
            run = self.get(run_id)
            if run.status in TERMINAL_STATUSES:
                return run
            if run.status in PAUSED_STATUSES:
                request = _follow_request(run, email_cap_usd=email_cap_usd) if follow else None
                if request is None:
                    return run
                self.continue_(run_id, request)
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
        while True:
            run = await self.get(run_id, ContactsRunGetParams(rows_offset=len(rows), rows_limit=page_size))
            rows.extend(run.rows)
            if not run.rows or len(rows) >= run.rows_total:
                return rows

    @api_route("POST", RUN_PATH + "/{run_id}/continue", openapi=False)
    async def continue_(self, run_id: str | UUID, request: ContinueRunRequest) -> ContactsRun:
        response = await self._transport.request("POST", _path(run_id) + "/continue", json_body=request.to_wire())
        return ContactsRun.model_validate(response.json())

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
        follow: bool = False,
        email_cap_usd: Decimal | float | None = None,
        max_wait: float = DEFAULT_MAX_WAIT_SECONDS,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> ContactsRun:
        deadline = _deadline(max_wait, poll_interval)
        while True:
            run = await self.get(run_id)
            if run.status in TERMINAL_STATUSES:
                return run
            if run.status in PAUSED_STATUSES:
                request = _follow_request(run, email_cap_usd=email_cap_usd) if follow else None
                if request is None:
                    return run
                await self.continue_(run_id, request)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise JobTimeoutError("Timed out waiting for the contacts run; it continues on the server")
            await asyncio.sleep(min(poll_interval, remaining))
