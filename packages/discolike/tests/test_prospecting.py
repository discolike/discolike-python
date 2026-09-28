from __future__ import annotations

import json
from uuid import UUID

import httpx2
import pytest
from pydantic import ValidationError

import discolike.resources.prospecting as module
from discolike import CHECKPOINT_STOP_REASONS
from discolike import JobTimeoutError
from discolike.requests import ProspectingApproveRequest
from discolike.requests import ProspectingBrief
from discolike.requests import ProspectingGetParams
from discolike.requests import ProspectingListParams
from discolike.requests import ProspectingMessageRequest
from discolike_testkit import AsyncClientFactory
from discolike_testkit import ClientFactory
from discolike_testkit.prospecting import message_payload
from discolike_testkit.prospecting import run_payload
from discolike_testkit.prospecting import summary_payload

RUN_ID = "00000000-0000-0000-0000-000000000001"
OTHER_QUERY_ID = "00000000-0000-0000-0000-000000000002"


def payload(status: str = "queued") -> dict:
    return run_payload(status)


def test_start_key_does_not_leak_to_other_requests(make_client: ClientFactory) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(202 if request.method == "POST" else 200, json=payload())

    with make_client(handler) as client:
        brief = ProspectingBrief(brief="US logistics companies and operations leaders")
        first = client.prospecting.start(brief, idempotency_key="stable-key")
        second = client.prospecting.start(brief, idempotency_key="stable-key")
        assert first.run_id == second.run_id == UUID(RUN_ID)
        client.prospecting.get(RUN_ID, ProspectingGetParams(offset=100, limit=25))
    assert [r.headers.get("Idempotency-Key") for r in seen] == ["stable-key", "stable-key", None]
    assert json.loads(seen[0].content) == {"brief": brief.brief}
    assert dict(seen[2].url.params) == {"offset": "100", "limit": "25"}


@pytest.mark.parametrize("status", ["completed", "needs_input", "failed", "cancelled"])
def test_wait_preserves_terminal_partial_results(make_client: ClientFactory, status: str) -> None:
    with make_client(lambda request: httpx2.Response(200, json=payload(status))) as client:
        run = client.prospecting.wait(RUN_ID)
    assert run.status == status
    assert run.companies == [{"domain": "example.com"}]


def test_wait_timeout_never_cancels(make_client: ClientFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    times = iter([0.0, 2.0])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(times))
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request.method)
        return httpx2.Response(200, json=payload())

    with make_client(handler) as client, pytest.raises(JobTimeoutError):
        client.prospecting.wait(RUN_ID, max_wait=1)
    assert seen == ["GET"]


@pytest.mark.parametrize("key", ["", " ", "a" * 129, "a\nb", "a\rb", "a\tb", "a\x00b", "a🚀b"])
def test_invalid_key_is_rejected_locally(make_client: ClientFactory, key: str) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        pytest.fail("invalid key must not reach the network")

    with make_client(handler) as client, pytest.raises(ValueError, match="idempotency_key"):
        client.prospecting.start(ProspectingBrief(brief="Logistics companies and buyers"), idempotency_key=key)


async def test_async_start_wait_and_cancel(make_async_client: AsyncClientFactory) -> None:
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request.method)
        if request.method == "POST":
            assert request.headers["Idempotency-Key"] == "async-key"
        return httpx2.Response(200, json=payload("cancelled" if request.method == "DELETE" else "completed"))

    async with make_async_client(handler) as client:
        run = await client.prospecting.start(
            ProspectingBrief(brief="Logistics companies and operations leaders"), idempotency_key="async-key"
        )
        assert (await client.prospecting.wait(run.run_id)).status == "completed"
        assert (await client.prospecting.cancel(run.run_id)).status == "cancelled"
    assert seen == ["POST", "GET", "DELETE"]


def test_wait_returns_a_proposed_plan(make_client: ClientFactory) -> None:
    with make_client(lambda request: httpx2.Response(200, json=payload("proposed"))) as client:
        assert client.prospecting.wait(RUN_ID).status == "proposed"


def test_list_approve_message_and_cursors(make_client: ClientFactory) -> None:
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        if request.url.path.endswith("/messages"):
            return httpx2.Response(202, json=message_payload())
        if request.url.path.endswith("/runs"):
            return httpx2.Response(200, json=[summary_payload()])
        result = payload("queued" if request.url.path.endswith("/approve") else "running")
        result.update(
            messages=[message_payload()],
            next_message_seq=8,
            next_event_seq=12,
            in_flight=[
                {
                    "stage": "generate",
                    "items": 50,
                    "plan_version": 2,
                    "state": "running",
                    "started_at": result["created_at"],
                }
            ],
            saved_query_id=RUN_ID,
            saved_query_ids=[RUN_ID, OTHER_QUERY_ID],
            plan_version=2,
            approved_plan_version=2,
            reply_pending=True,
            fit_companies=40,
            emails_found=15,
            chat_closed=True,
            stop_reason="misuse",
        )
        return httpx2.Response(200, json=result)

    with make_client(handler) as client:
        assert client.prospecting.list(ProspectingListParams(limit=50, before=RUN_ID))[0].target_companies == 25
        assert client.prospecting.approve(RUN_ID, ProspectingApproveRequest(plan_version=2)).approved_plan_version == 2
        assert (
            client.prospecting.message(
                RUN_ID, ProspectingMessageRequest(text="Make it 100 companies"), idempotency_key="message-1"
            ).seq
            == 8
        )
        run = client.prospecting.get(RUN_ID, ProspectingGetParams(events_after=12, messages_after=8, limit=500))
    assert dict(seen[0].url.params) == {"limit": "50", "before": RUN_ID}
    assert json.loads(seen[1].content) == {"plan_version": 2}
    assert json.loads(seen[2].content) == {"text": "Make it 100 companies"}
    assert [r.headers.get("Idempotency-Key") for r in seen] == [None, None, "message-1", None]
    assert dict(seen[3].url.params) == {"events_after": "12", "messages_after": "8", "limit": "500"}
    assert run.messages[0].created_at.year == 2026
    assert run.in_flight[0].stage == "generate"
    assert run.saved_query_id == UUID(RUN_ID)
    assert run.saved_query_ids == [UUID(RUN_ID), UUID(OTHER_QUERY_ID)]
    assert (run.fit_companies, run.emails_found, run.reply_pending) == (40, 15, True)
    assert (run.chat_closed, run.stop_reason) == (True, "misuse")


async def test_async_chat_lifecycle_and_proposed_wait(make_async_client: AsyncClientFactory) -> None:
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        if request.url.path.endswith("/messages"):
            return httpx2.Response(202, json=message_payload())
        if request.url.path.endswith("/runs"):
            return httpx2.Response(200, json=[summary_payload()])
        return httpx2.Response(200, json=payload("queued" if request.method == "POST" else "proposed"))

    async with make_async_client(handler) as client:
        assert len(await client.prospecting.list()) == 1
        assert (await client.prospecting.wait(RUN_ID)).status == "proposed"
        assert (await client.prospecting.approve(RUN_ID, ProspectingApproveRequest(plan_version=1))).status == "queued"
        message = await client.prospecting.message(
            RUN_ID, ProspectingMessageRequest(text="Make it 100 companies"), idempotency_key="async-message"
        )
        await client.prospecting.get(RUN_ID, ProspectingGetParams(events_after=7, messages_after=message.seq))
    assert seen[0].url.params == httpx2.QueryParams()
    assert json.loads(seen[2].content) == {"plan_version": 1}
    assert seen[3].headers["Idempotency-Key"] == "async-message"
    assert json.loads(seen[3].content) == {"text": "Make it 100 companies"}
    assert dict(seen[4].url.params) == {"events_after": "7", "messages_after": "8"}
    assert seen[4].headers.get("Idempotency-Key") is None


@pytest.mark.parametrize("key", ["", " ", "a" * 129, "a\nb", "a\rb", "a\tb", "a\x00b", "a🚀b"])
def test_invalid_message_key_never_reaches_network(make_client: ClientFactory, key: str) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        pytest.fail("invalid key must fail locally")

    with make_client(handler) as client, pytest.raises(ValueError, match="idempotency_key"):
        client.prospecting.message(RUN_ID, ProspectingMessageRequest(text="Continue"), idempotency_key=key)


@pytest.mark.parametrize(
    ("model", "values"),
    [
        (ProspectingApproveRequest, {}),
        (ProspectingApproveRequest, {"plan_version": 0}),
        (ProspectingApproveRequest, {"plan_version": 1, "checkpoints": "sometimes"}),
        (ProspectingBrief, {"brief": "US logistics companies", "checkpoints": "never"}),
        (ProspectingListParams, {"limit": 51}),
        (ProspectingListParams, {"limit": 0}),
        (ProspectingListParams, {"before": "not-a-uuid"}),
        (ProspectingMessageRequest, {"text": ""}),
        (ProspectingMessageRequest, {"text": "x" * 4001}),
        (ProspectingGetParams, {"events_after": -1}),
        (ProspectingGetParams, {"messages_after": -1}),
    ],
)
def test_chat_request_constraints(model, values) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(values)


def test_request_defaults_preserve_explicit_quantity_intent() -> None:
    implicit = ProspectingBrief(brief="Find 1000 companies and three founders each")
    explicit = ProspectingBrief(
        brief=implicit.brief, target_companies=25, contacts_per_company=2, max_actions=0, max_candidates=0
    )
    assert implicit.to_wire() == {"brief": implicit.brief}
    assert explicit.to_wire() == {
        "brief": implicit.brief,
        "target_companies": 25,
        "contacts_per_company": 2,
        "max_actions": 0,
        "max_candidates": 0,
    }
    assert (ProspectingListParams().limit, ProspectingListParams().before) == (20, None)


def test_checkpoints_default_to_the_server_mode_and_send_only_when_set() -> None:
    brief = "US logistics companies and operations leaders"
    assert ProspectingBrief(brief=brief).checkpoints == "auto"
    assert ProspectingBrief(brief=brief).to_wire() == {"brief": brief}
    assert ProspectingBrief(brief=brief, checkpoints="ask").to_wire() == {"brief": brief, "checkpoints": "ask"}
    assert ProspectingApproveRequest(plan_version=2).to_wire() == {"plan_version": 2}
    assert ProspectingApproveRequest(plan_version=2, checkpoints="auto").to_wire() == {
        "plan_version": 2,
        "checkpoints": "auto",
    }


def test_wait_returns_at_a_checkpoint_with_its_question(make_client: ClientFactory) -> None:
    question = message_payload() | {
        "role": "agent",
        "kind": "question",
        "content": "Found 25 companies and 50 emails. Want more?",
        "data": {"reason": "target_reached", "suggested_replies": ["That's enough", "Find 25 more"], "sample": []},
    }
    paused = payload("needs_input") | {
        "stop_reason": "target_reached",
        "brief": {"brief": "US logistics companies and operations leaders", "checkpoints": "ask"},
        "messages": [question],
    }
    with make_client(lambda request: httpx2.Response(200, json=paused)) as client:
        run = client.prospecting.wait(RUN_ID)
    assert (run.status, run.stop_reason) == ("needs_input", "target_reached")
    assert run.stop_reason in CHECKPOINT_STOP_REASONS
    assert run.brief.checkpoints == "ask"
    assert run.messages[-1].data == question["data"]


def test_a_failed_pilot_carries_its_sample(make_client: ClientFactory) -> None:
    sample = [{"domain": "example.com", "name": "Example", "company_fit": "No", "reason": "Sells software"}]
    stopped = payload("completed") | {"stop_reason": "pilot_failed", "pilot_sample": sample}
    with make_client(lambda request: httpx2.Response(200, json=stopped)) as client:
        run = client.prospecting.wait(RUN_ID)
    assert (run.stop_reason, run.pilot_sample) == ("pilot_failed", sample)
    assert run.companies_saved_query_id is None
    assert run.stop_reason not in CHECKPOINT_STOP_REASONS


def test_a_run_carries_its_saved_companies_list(make_client: ClientFactory) -> None:
    completed = payload("completed") | {"saved_query_id": RUN_ID, "companies_saved_query_id": OTHER_QUERY_ID}
    with make_client(lambda request: httpx2.Response(200, json=completed)) as client:
        assert client.prospecting.get(RUN_ID).companies_saved_query_id == UUID(OTHER_QUERY_ID)


def test_a_run_from_a_newer_server_still_parses(make_client: ClientFactory) -> None:
    newer = payload("archived") | {
        "brief": {"brief": "Dentists", "contacts_per_company": 50, "target_companies": 50_000, "checkpoints": "review"},
        "messages": [message_payload() | {"kind": "chart", "role": "system"}],
    }
    with make_client(lambda request: httpx2.Response(200, json=newer)) as client:
        run = client.prospecting.get(RUN_ID)
    assert (run.status, run.brief.contacts_per_company, run.messages[0].kind) == ("archived", 50, "chart")


def test_a_summary_keeps_a_brief_longer_than_the_list_preview() -> None:
    summary = module.ProspectingRunSummary.model_validate(summary_payload() | {"brief": "x" * 500})
    assert len(summary.brief) == 500
