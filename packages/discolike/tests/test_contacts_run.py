from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import httpx2
import pytest

import discolike.resources.contacts_run as module
from discolike.requests import ContactsRunGetParams
from discolike.requests import ContactsRunListParams
from discolike.requests import ContactsRunRequest
from discolike.requests import ContinueRunRequest
from discolike.requests import TitlePreviewRequest
from discolike.resources.contacts_run import ContactsRun
from discolike_testkit import AsyncClientFactory
from discolike_testkit import ClientFactory

RUN_ID = "00000000-0000-0000-0000-0000000000aa"
RUN_PATH = f"/v1/contacts/run/{RUN_ID}"
TIMESTAMP = "2026-10-30T12:00:00Z"


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)

    async def fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)


def run_payload(
    *,
    status: str = "waiting",
    current_step: str = "find_contacts",
    step_status: str = "done",
    generation: int = 1,
    rows: list[dict[str, Any]] | None = None,
    rows_total: int = 0,
) -> dict[str, Any]:
    return {
        "input": {"people": {"titles": ["Owner"]}},
        "id": RUN_ID,
        "kind": "contacts",
        "status": status,
        "current_step": current_step,
        "generation": generation,
        "steps": {current_step: {"status": step_status, "estimate_usd": "1.50", "charged_usd": "0.75"}},
        "total_estimate_usd": "1.50",
        "total_charged_usd": "0.75",
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "expires_at": "2026-11-29T12:00:00Z",
        "rows": rows or [],
        "rows_total": rows_total,
        "future_field": True,
    }


def row(key: str) -> dict[str, Any]:
    return {"row_key": key, "domain": "acme.com", "name": "Jane Doe", "source": "database"}


def request() -> ContactsRunRequest:
    return ContactsRunRequest.model_validate(
        {"companies": {"source": "domains", "domains": ["acme.com"]}, "people": {"titles": ["Owner"]}}
    )


class StepServer:
    """Fake run server: each continue enters the next step, which finishes and waits."""

    order = ("find_contacts", "find_missing", "review", "find_emails")

    def __init__(self) -> None:
        self.step = 0
        self.generation = 1
        self.continues: list[dict[str, Any]] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        if request.method == "POST" and request.url.path.endswith("/continue"):
            self.continues.append(json.loads(request.content))
            self.step += 1
            self.generation += 1
        last = self.step == len(self.order) - 1
        return httpx2.Response(
            200,
            json=run_payload(
                status="done" if last else "waiting",
                current_step=self.order[self.step],
                generation=self.generation,
            ),
        )


def test_create_posts_body_and_parses_run(make_client: ClientFactory) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(202, json=run_payload(status="running", step_status="running"))

    with make_client(handler) as client:
        run = client.contacts_run.create(request())

    assert seen[0].method == "POST"
    assert seen[0].url.path == "/v1/contacts/run"
    assert json.loads(seen[0].content) == {
        "companies": {"source": "domains", "domains": ["acme.com"]},
        "people": {"titles": ["Owner"]},
    }
    assert isinstance(run, ContactsRun)
    assert run.status == "running"
    assert run.steps["find_contacts"].estimate_usd == Decimal("1.50")
    assert run.total_charged_usd == Decimal("0.75")
    assert run.model_extra == {"future_field": True}


def test_prompt_companies_default_to_500() -> None:
    body = ContactsRunRequest.model_validate(
        {"companies": {"source": "prompt", "icp_text": "dental clinics"}, "people": {"titles": ["Owner"]}}
    )
    assert body.companies.max_companies == 500  # ty: ignore[unresolved-attribute]


def test_continue_sends_generation(make_client: ClientFactory) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(202, json=run_payload(status="running", current_step="find_missing", generation=3))

    with make_client(handler) as client:
        run = client.contacts_run.continue_(RUN_ID, ContinueRunRequest(generation=2, relevance="max_coverage"))

    assert seen[0].url.path == f"{RUN_PATH}/continue"
    assert json.loads(seen[0].content) == {"generation": 2, "relevance": "max_coverage"}
    assert run.generation == 3


def test_get_list_cancel_and_title_preview_routes(make_client: ClientFactory) -> None:
    seen: list[tuple[str, str, str]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append((request.method, request.url.path, request.url.query.decode()))
        if request.url.path.endswith("title-preview"):
            return httpx2.Response(200, json={"titles": [{"title": "Owner", "role": 0.9, "count": 12}]})
        if request.url.path == "/v1/contacts/run":
            return httpx2.Response(200, json=[run_payload()])
        return httpx2.Response(200, json=run_payload(status="cancelled"))

    with make_client(handler) as client:
        client.contacts_run.get(RUN_ID, ContactsRunGetParams(rows_offset=100, rows_limit=50))
        client.contacts_run.list(ContactsRunListParams(limit=5))
        client.contacts_run.cancel(RUN_ID)
        preview = client.contacts_run.title_preview(TitlePreviewRequest(titles=["Owner"], match="similar"))

    assert seen == [
        ("GET", RUN_PATH, "rows_offset=100&rows_limit=50"),
        ("GET", "/v1/contacts/run", "limit=5"),
        ("POST", f"{RUN_PATH}/cancel", ""),
        ("POST", "/v1/contacts/run/title-preview", ""),
    ]
    assert preview.titles[0].count == 12


def test_wait_without_follow_returns_paused_run(make_client: ClientFactory) -> None:
    server = StepServer()
    with make_client(server) as client:
        run = client.contacts_run.wait(RUN_ID)
    assert run.status == "waiting"
    assert server.continues == []


def test_wait_follow_stops_before_emails_without_cap(make_client: ClientFactory) -> None:
    server = StepServer()
    with make_client(server) as client:
        run = client.contacts_run.wait(RUN_ID, follow=True)
    assert run.status == "waiting"
    assert run.current_step == "review"
    assert server.continues == [{"generation": 1}, {"generation": 2}]


def test_wait_follow_continues_into_emails_with_cap(make_client: ClientFactory) -> None:
    server = StepServer()
    with make_client(server) as client:
        run = client.contacts_run.wait(RUN_ID, follow=True, email_cap_usd=25)
    assert run.status == "done"
    assert run.current_step == "find_emails"
    assert server.continues == [{"generation": 1}, {"generation": 2}, {"generation": 3, "email_cap_usd": "25"}]


def test_wait_follow_enters_emails_with_the_cap_set_at_create(make_client: ClientFactory) -> None:
    server = StepServer()

    def handler(request: httpx2.Request) -> httpx2.Response:
        response = server(request)
        return httpx2.Response(200, json={**response.json(), "input": {"email_cap_usd": "30"}})

    with make_client(handler) as client:
        run = client.contacts_run.wait(RUN_ID, follow=True)
    assert run.status == "done"
    assert server.continues == [{"generation": 1}, {"generation": 2}, {"generation": 3}]


def test_wait_follow_stops_at_a_failed_step(make_client: ClientFactory) -> None:
    seen: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request.method)
        return httpx2.Response(200, json=run_payload(step_status="failed"))

    with make_client(handler) as client:
        run = client.contacts_run.wait(RUN_ID, follow=True, email_cap_usd=25)
    assert run.steps["find_contacts"].status == "failed"
    assert seen == ["GET"]


def test_rows_pages_until_total(make_client: ClientFactory) -> None:
    offsets: list[str | None] = []
    all_rows = [row(f"r{i}") for i in range(5)]

    def handler(request: httpx2.Request) -> httpx2.Response:
        offset = int(request.url.params["rows_offset"])
        limit = int(request.url.params["rows_limit"])
        offsets.append(request.url.params["rows_offset"])
        return httpx2.Response(200, json=run_payload(rows=all_rows[offset : offset + limit], rows_total=5))

    with make_client(handler) as client:
        rows = client.contacts_run.rows(RUN_ID, page_size=2)

    assert [item.row_key for item in rows] == ["r0", "r1", "r2", "r3", "r4"]
    assert offsets == ["0", "2", "4"]


async def test_async_create_and_wait_follow(make_async_client: AsyncClientFactory) -> None:
    server = StepServer()

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/v1/contacts/run":
            return httpx2.Response(202, json=run_payload(status="running", step_status="running"))
        return server(request)

    async with make_async_client(handler) as client:
        created = await client.contacts_run.create(request())
        run = await client.contacts_run.wait(created.id, follow=True)
    assert run.current_step == "review"
    assert server.continues == [{"generation": 1}, {"generation": 2}]
