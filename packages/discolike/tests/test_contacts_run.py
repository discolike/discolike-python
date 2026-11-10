from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import httpx2
import pydantic
import pytest

import discolike.resources.contacts_run as module
from discolike import InsufficientBalanceError
from discolike import JobTimeoutError
from discolike.requests import ContactsRunEventsParams
from discolike.requests import ContactsRunGetParams
from discolike.requests import ContactsRunListParams
from discolike.requests import ContactsRunRequest
from discolike.requests import ContinueRunRequest
from discolike.requests import TitlePreviewRequest
from discolike.resources.contacts_run import ContactsRun
from discolike.resources.contacts_run import ContactsRunEventsResponse
from discolike_testkit import AsyncClientFactory
from discolike_testkit import ClientFactory

RUN_ID = "00000000-0000-0000-0000-0000000000aa"
RUN_PATH = f"/v1/contacts/run/{RUN_ID}"
TIMESTAMP = "2026-10-30T12:00:00Z"


def run_payload(status: str = "running", **extra: Any) -> dict[str, Any]:
    return {
        "id": RUN_ID,
        "kind": "contacts",
        "status": status,
        "generation": 1,
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
        "expires_at": TIMESTAMP,
        **extra,
    }


def request() -> ContactsRunRequest:
    return ContactsRunRequest.model_validate(
        {
            "companies": {"source": "domains", "domains": ["acme.com"]},
            "people": {"fit": "Owners"},
        }
    )


def test_create_wire_and_open_response(make_client: ClientFactory) -> None:
    seen: list[httpx2.Request] = []

    def handler(req: httpx2.Request) -> httpx2.Response:
        seen.append(req)
        return httpx2.Response(
            202,
            json=run_payload(
                companies=[
                    {
                        "domain": "Company 1",
                        "status": "future",
                        "future": True,
                        "contacts": [
                            {"row_key": "r1", "domain": "Company 1", "email_status": "Validated (catch-all resolved)"},
                        ],
                    }
                ],
                companies_total=1,
                summary={"companies_delivered": 1, "validated_contacts": 1, "spent_usd": "0.10"},
                future=True,
            ),
        )

    with make_client(handler) as client:
        run = client.contacts_run.create(request())
    assert seen[0].url.path == "/v1/contacts/run"
    assert json.loads(seen[0].content) == request().to_wire()
    assert run.current_step is None
    assert run.companies[0].contacts[0].email_state is None
    assert run.companies[0].contacts[0].email_status == "Validated (catch-all resolved)"
    assert run.summary is not None
    assert run.summary.spent_usd == Decimal("0.10")
    assert run.model_extra == {"future": True}
    assert run.companies[0].model_extra == {"future": True}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("start", True),
        ("max_contacts", 5),
        ("auto_stop", False),
        ("find_missing", {}),
        ("mode", "run_all"),
    ],
)
def test_removed_fields_rejected(field: str, value: Any) -> None:
    with pytest.raises(pydantic.ValidationError):
        ContactsRunRequest.model_validate(request().to_wire() | {field: value})


def test_request_defaults_and_supported_fields() -> None:
    body = ContactsRunRequest.model_validate(
        {
            "companies": {"source": "prompt", "filters": {"filter_country": ["US"]}},
            "max_companies": 15,
            "per_company": 3,
            "email_cap_usd": "12.50",
            "create_key": "key",
            "exclude_domains": ["acme.com"],
            "exclude_query_ids": ["query"],
            "relevance": "max_coverage",
        }
    )
    assert body.people.fit == "Senior executives and decision makers"
    assert body.to_wire()["max_companies"] == 15
    assert "people" not in body.to_wire()
    with pytest.raises(pydantic.ValidationError):
        ContactsRunRequest.model_validate(request().to_wire() | {"people": {"titles": ["Owner"]}})
    with pytest.raises(pydantic.ValidationError):
        ContactsRunRequest.model_validate(request().to_wire() | {"per_company": "all"})
    assert ContactsRunRequest.model_validate({"companies": {"source": "lookalike", "persona_ids": [1]}})


def test_live_routes(make_client: ClientFactory) -> None:
    seen: list[tuple[str, str, dict[str, Any]]] = []

    def handler(req: httpx2.Request) -> httpx2.Response:
        seen.append((req.method, req.url.path, json.loads(req.content) if req.content else dict(req.url.params)))
        if req.url.path.endswith("title-preview"):
            return httpx2.Response(200, json={"titles": [], "searched": ["Owner"]})
        if req.url.path.endswith("events"):
            return httpx2.Response(200, json={"events": [], "next_cursor": 5})
        return httpx2.Response(200, json=[run_payload()] if req.url.path == "/v1/contacts/run" else run_payload())

    with make_client(handler) as client:
        client.contacts_run.get(RUN_ID, ContactsRunGetParams(rows_offset=2, rows_limit=3))
        client.contacts_run.list(ContactsRunListParams(limit=5))
        client.contacts_run.cancel(RUN_ID)
        client.contacts_run.continue_(RUN_ID, ContinueRunRequest(generation=2, redo=True))
        client.contacts_run.title_preview(TitlePreviewRequest(titles=["Owner"], match="similar", relevance="balanced"))
        assert client.contacts_run.events(RUN_ID, ContactsRunEventsParams(after=4, limit=10)).next_cursor == 5
    assert seen == [
        ("GET", RUN_PATH, {"rows_offset": "2", "rows_limit": "3"}),
        ("GET", "/v1/contacts/run", {"limit": "5"}),
        ("POST", RUN_PATH + "/cancel", {}),
        ("POST", RUN_PATH + "/continue", {"generation": 2, "redo": True}),
        ("POST", "/v1/contacts/run/title-preview", {"titles": ["Owner"], "match": "similar", "relevance": "balanced"}),
        ("GET", RUN_PATH + "/events", {"after": "4", "limit": "10"}),
    ]


def test_open_events() -> None:
    page = ContactsRunEventsResponse.model_validate(
        {
            "next_cursor": 1,
            "future": True,
            "events": [
                {
                    "seq": 1,
                    "domain": "Company 1",
                    "created_at": TIMESTAMP,
                    "kind": "future",
                    "status": "future",
                    "validated_titles": [{"title": "Owner", "status": "future", "future": True}],
                    "future": True,
                }
            ],
        }
    )
    assert page.events[0].company_name is None
    assert page.events[0].validated_titles[0].status == "future"
    assert (
        module.ContactsRunEvent.model_validate(page.events[0].model_dump() | {"company_name": "Acme"}).company_name
        == "Acme"
    )
    assert ContactsRun.model_validate(
        run_payload("future", current_step="future", steps={"future": {"status": "future"}})
    )


@pytest.mark.parametrize("terminal", ["done", "failed", "cancelled"])
def test_wait_only_polls(make_client: ClientFactory, monkeypatch: pytest.MonkeyPatch, terminal: str) -> None:
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    statuses = iter(["ready", "running", terminal])

    def handler(req: httpx2.Request) -> httpx2.Response:
        assert req.method == "GET"
        return httpx2.Response(200, json=run_payload(next(statuses)))

    with make_client(handler) as client:
        assert client.contacts_run.wait(RUN_ID).status == terminal


def test_wait_timeout(make_client: ClientFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "_deadline", lambda *_: 0)
    with make_client(lambda _: httpx2.Response(200, json=run_payload())) as client:
        with pytest.raises(JobTimeoutError):
            client.contacts_run.wait(RUN_ID)


def company_page(req: httpx2.Request, *, kind: str = "contacts") -> httpx2.Response:
    offset = int(req.url.params["rows_offset"])
    pages = [
        {"domain": "Company 1", "status": "skipped", "contacts": []},
        {
            "domain": "Company 2",
            "status": "validated",
            "contacts": [
                {"row_key": "a", "domain": "Company 2"},
                {"row_key": "b", "domain": "Company 2"},
            ],
        },
        {"domain": "Company 3", "status": "validated", "contacts": [{"row_key": "c", "domain": "Company 3"}]},
    ]
    assert req.url.params["rows_limit"] == "1"
    return httpx2.Response(
        200, json=run_payload(kind=kind, companies=pages[offset : offset + 1], companies_total=3, contacts_total=3)
    )


@pytest.mark.parametrize("kind", ["contacts", "companies"])
def test_rows_pages_domains_including_empty_companies(make_client: ClientFactory, kind: str) -> None:
    with make_client(lambda req: company_page(req, kind=kind)) as client:
        assert [r.row_key for r in client.contacts_run.rows(RUN_ID, page_size=1)] == ["a", "b", "c"]


@pytest.mark.parametrize("kind", ["contacts", "companies"])
async def test_async_rows(make_async_client: AsyncClientFactory, kind: str) -> None:
    async with make_async_client(lambda req: company_page(req, kind=kind)) as client:
        assert [r.row_key for r in await client.contacts_run.rows(RUN_ID, page_size=1)] == ["a", "b", "c"]


async def test_async_create_wait_events_cancel(
    make_async_client: AsyncClientFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def no_sleep(_: float) -> None:
        pass

    monkeypatch.setattr(module.asyncio, "sleep", no_sleep)
    statuses = iter(["ready", "running", "done"])

    def handler(req: httpx2.Request) -> httpx2.Response:
        if req.url.path.endswith("events"):
            assert req.url.params["after"] == "5"
            return httpx2.Response(200, json={"events": [], "next_cursor": 6})
        if req.url.path.endswith("cancel"):
            return httpx2.Response(200, json=run_payload("cancelled"))
        if req.method == "POST":
            assert json.loads(req.content) == request().to_wire()
            return httpx2.Response(202, json=run_payload())
        return httpx2.Response(200, json=run_payload(next(statuses)))

    async with make_async_client(handler) as client:
        created = await client.contacts_run.create(request())
        assert (await client.contacts_run.wait(created.id)).status == "done"
        assert (await client.contacts_run.events(created.id, ContactsRunEventsParams(after=5))).next_cursor == 6
        assert (await client.contacts_run.cancel(created.id)).status == "cancelled"


def test_insufficient_balance(make_client: ClientFactory) -> None:
    with make_client(
        lambda _: httpx2.Response(
            403,
            json={
                "detail": {
                    "code": "INSUFFICIENT_BALANCE",
                    "message": "Too expensive",
                    "remaining_usd": "1.00",
                    "max_affordable_records": 2,
                }
            },
        )
    ) as client:
        with pytest.raises(InsufficientBalanceError) as exc:
            client.contacts_run.create(request())
    assert exc.value.max_affordable_records == 2


def test_response_fields_accept_new_server_values() -> None:
    run = ContactsRun.model_validate(
        run_payload(
            applied_company_filters={
                "filter_industry": ["+FUTURE"],
                "negate_filter_industry": ["FUTURE"],
                "sub_industry": ["FUTURE"] * 100,
                "future": True,
            },
            contacts_total=2,
            progress={"future": 3},
            summary={"skipped_no_mx": -1, "stop_reason": "future"},
            companies=[
                {
                    "domain": "acme.com",
                    "status": "future",
                    "company": {"name": "Acme", "future": True},
                    "contacts": [{"domain": "acme.com", "row_key": "a", "email_state": "future", "future": True}],
                }
            ],
        )
    )
    assert run.contacts_total == 2
    assert run.progress == {"future": 3}
    assert run.applied_company_filters is not None
    assert run.applied_company_filters.negate_filter_industry == ["FUTURE"]
    assert run.applied_company_filters.model_extra == {"future": True}
    assert run.summary is not None
    assert run.summary.skipped_no_mx == -1
    assert run.summary.stop_reason == "future"
    assert run.companies[0].company == {"name": "Acme", "future": True}
    assert run.companies[0].contacts[0].email_state == "future"
    assert run.companies[0].contacts[0].model_extra == {"future": True}


def test_response_fields_default_for_older_servers() -> None:
    run = ContactsRun.model_validate(run_payload())
    assert run.applied_company_filters is None
    assert run.contacts_total == 0
    assert run.progress == {}
    summary = module.ContactsRunSummary()
    assert summary.skipped_no_mx is None
    assert summary.stop_reason is None
    company = module.RunCompanyResponse(domain="acme.com", status="pending")
    assert company.company == {}
    assert not {"rows", "rows_total"} & ContactsRun.model_fields.keys()
    assert not {"child_task_id", "state"} & module.ContactsRunStep.model_fields.keys()
    assert not {"company", "source"} & module.ContactsRunRow.model_fields.keys()
