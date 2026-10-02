from __future__ import annotations

import json
from uuid import UUID

import httpx2
import pytest
from pydantic import ValidationError

import discolike.resources.prospecting as module
from discolike import CHECKPOINT_STOP_REASONS
from discolike import DiscolikeError
from discolike import JobTimeoutError
from discolike import NotFoundError
from discolike.requests import IntakeAnswer
from discolike.requests import ProspectingApproveRequest
from discolike.requests import ProspectingBrief
from discolike.requests import ProspectingGetParams
from discolike.requests import ProspectingListParams
from discolike.requests import ProspectingMessageRequest
from discolike.requests import ProspectingPlanSettings
from discolike.requests import ProspectingRunUpdate
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
        seen.append((request.method, request.url.path))
        if request.url.path.endswith("/cancel"):
            return httpx2.Response(200, json=payload("cancelled"))
        if request.method == "POST":
            assert request.headers["Idempotency-Key"] == "async-key"
        return httpx2.Response(200, json=payload("completed"))

    async with make_async_client(handler) as client:
        run = await client.prospecting.start(
            ProspectingBrief(brief="Logistics companies and operations leaders"), idempotency_key="async-key"
        )
        assert (await client.prospecting.wait(run.run_id)).status == "completed"
        assert (await client.prospecting.cancel(run.run_id)).status == "cancelled"
    assert seen == [
        ("POST", "/v1/prospecting/runs"),
        ("GET", f"/v1/prospecting/runs/{RUN_ID}"),
        ("POST", f"/v1/prospecting/runs/{RUN_ID}/cancel"),
    ]


def test_cancel_posts_to_the_cancel_route(make_client: ClientFactory) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=payload("cancelled"))

    with make_client(handler) as client:
        assert client.prospecting.cancel(RUN_ID).status == "cancelled"
    assert [(r.method, r.url.path) for r in seen] == [("POST", f"/v1/prospecting/runs/{RUN_ID}/cancel")]
    assert seen[0].content == b""


def test_delete_hides_the_run_and_returns_nothing(make_client: ClientFactory) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        if request.method == "DELETE":
            return httpx2.Response(204)
        return httpx2.Response(404, json={"detail": "Prospecting run not found"})

    with make_client(handler) as client:
        assert client.prospecting.delete(RUN_ID) is None
        with pytest.raises(NotFoundError):
            client.prospecting.get(RUN_ID)
    assert [(r.method, r.url.path) for r in seen] == [
        ("DELETE", f"/v1/prospecting/runs/{RUN_ID}"),
        ("GET", f"/v1/prospecting/runs/{RUN_ID}"),
    ]


async def test_async_delete_returns_nothing(make_async_client: AsyncClientFactory) -> None:
    seen: list[tuple[str, str]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append((request.method, request.url.path))
        return httpx2.Response(204)

    async with make_async_client(handler) as client:
        assert await client.prospecting.delete(RUN_ID) is None
    assert seen == [("DELETE", f"/v1/prospecting/runs/{RUN_ID}")]


def test_rename_patches_the_title_and_returns_the_summary(make_client: ClientFactory) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=summary_payload() | {"title": "Logistics ops leaders"})

    with make_client(handler) as client:
        summary = client.prospecting.rename(RUN_ID, ProspectingRunUpdate(title="  Logistics ops leaders "))
    assert isinstance(summary, module.ProspectingRunSummary)
    assert summary.title == "Logistics ops leaders"
    assert [(r.method, r.url.path) for r in seen] == [("PATCH", f"/v1/prospecting/runs/{RUN_ID}")]
    assert json.loads(seen[0].content) == {"title": "  Logistics ops leaders "}


def test_rename_switches_the_checkpoint_mode_without_a_title(make_client: ClientFactory) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=summary_payload())

    with make_client(handler) as client:
        summary = client.prospecting.rename(RUN_ID, ProspectingRunUpdate(checkpoints="auto"))
    assert summary.run_id == UUID(RUN_ID)
    assert json.loads(seen[0].content) == {"checkpoints": "auto"}


def test_rename_surfaces_a_finished_run_on_a_mode_switch(make_client: ClientFactory) -> None:
    with (
        make_client(lambda request: httpx2.Response(409, json={"detail": "This run has finished"})) as client,
        pytest.raises(DiscolikeError, match="This run has finished"),
    ):
        client.prospecting.rename(RUN_ID, ProspectingRunUpdate(checkpoints="ask"))


def test_run_update_rejects_an_unknown_checkpoint_mode_before_sending() -> None:
    with pytest.raises(ValidationError):
        ProspectingRunUpdate.model_validate({"checkpoints": "sometimes"})


def test_rename_surfaces_a_missing_run(make_client: ClientFactory) -> None:
    with (
        make_client(lambda request: httpx2.Response(404, json={"detail": "Prospecting run not found"})) as client,
        pytest.raises(NotFoundError),
    ):
        client.prospecting.rename(RUN_ID, ProspectingRunUpdate(title="Renamed"))


def test_rename_rejects_an_overlong_title_before_sending() -> None:
    with pytest.raises(ValidationError):
        ProspectingRunUpdate(title="x" * 81)


async def test_async_rename_patches_the_title(make_async_client: AsyncClientFactory) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=summary_payload() | {"title": "Renamed"})

    async with make_async_client(handler) as client:
        summary = await client.prospecting.rename(RUN_ID, ProspectingRunUpdate(title="Renamed"))
    assert summary.title == "Renamed"
    assert summary.run_id == UUID(RUN_ID)
    assert [(r.method, r.url.path) for r in seen] == [("PATCH", f"/v1/prospecting/runs/{RUN_ID}")]
    assert json.loads(seen[0].content) == {"title": "Renamed"}


def test_update_plan_patches_only_the_set_fields(make_client: ClientFactory) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=payload("proposed") | {"plan_version": 2})

    with make_client(handler) as client:
        run = client.prospecting.update_plan(
            RUN_ID, ProspectingPlanSettings(plan_version=1, search_provider_id="none", max_spend_usd=0)
        )
    assert run.plan_version == 2
    assert [(r.method, r.url.path) for r in seen] == [("PATCH", f"/v1/prospecting/runs/{RUN_ID}/plan")]
    assert json.loads(seen[0].content) == {"plan_version": 1, "search_provider_id": "none", "max_spend_usd": 0}


def test_update_plan_sends_run_shape_and_provider_limit(make_client: ClientFactory) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=payload("proposed") | {"plan_version": 2})

    settings = ProspectingPlanSettings(
        plan_version=1,
        target_companies=250,
        contacts_per_company=10,
        max_provider_spend_usd=12.5,
        deliverable="accounts",
        goal="companies",
    )
    with make_client(handler) as client:
        client.prospecting.update_plan(RUN_ID, settings)
    assert json.loads(seen[0].content) == {
        "plan_version": 1,
        "target_companies": 250,
        "contacts_per_company": 10,
        "max_provider_spend_usd": 12.5,
        "deliverable": "accounts",
        "goal": "companies",
    }


@pytest.mark.parametrize(
    "values",
    [
        {"deliverable": "people"},
        {"goal": "accounts"},
        {"max_provider_spend_usd": -1},
        {"target_companies": 0},
        {"contacts_per_company": 11},
    ],
)
def test_update_plan_rejects_bad_run_shape_locally(values: dict) -> None:
    with pytest.raises(ValidationError):
        ProspectingPlanSettings.model_validate({"plan_version": 1} | values)


@pytest.mark.parametrize("status", [409, 422])
def test_update_plan_surfaces_rejections(make_client: ClientFactory, status: int) -> None:
    with (
        make_client(lambda request: httpx2.Response(status, json={"detail": "rejected"})) as client,
        pytest.raises(DiscolikeError),
    ):
        client.prospecting.update_plan(RUN_ID, ProspectingPlanSettings(plan_version=1, contact_integration_id="x"))


def test_update_plan_validates_locally() -> None:
    with pytest.raises(ValidationError):
        ProspectingPlanSettings(plan_version=1, max_spend_usd=-1)
    with pytest.raises(ValidationError):
        ProspectingPlanSettings(plan_version=0)


async def test_async_update_plan_patches_the_plan(make_async_client: AsyncClientFactory) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=payload("proposed") | {"plan_version": 3})

    async with make_async_client(handler) as client:
        run = await client.prospecting.update_plan(RUN_ID, ProspectingPlanSettings(plan_version=2, max_spend_usd=25.0))
    assert run.plan_version == 3
    assert [(r.method, r.url.path) for r in seen] == [("PATCH", f"/v1/prospecting/runs/{RUN_ID}/plan")]
    assert json.loads(seen[0].content) == {"plan_version": 2, "max_spend_usd": 25.0}


@pytest.mark.parametrize(
    "reason", ["candidate_limit", "credit_limit", "provider_limit", "companies_worked", "a_reason_added_later"]
)
def test_stop_reason_stays_an_open_string(make_client: ClientFactory, reason: str) -> None:
    with make_client(
        lambda request: httpx2.Response(200, json=payload("completed") | {"stop_reason": reason})
    ) as client:
        assert client.prospecting.get(RUN_ID).stop_reason == reason


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
    assert (implicit.target_companies, implicit.contacts_per_company) == (1000, 3)
    assert implicit.to_wire() == {"brief": implicit.brief}
    assert explicit.to_wire() == {
        "brief": implicit.brief,
        "target_companies": 25,
        "contacts_per_company": 2,
        "max_actions": 0,
        "max_candidates": 0,
    }
    assert (ProspectingListParams().limit, ProspectingListParams().before) == (20, None)


def test_deliverable_and_goal_are_sent_only_when_set() -> None:
    brief = "US logistics companies and operations leaders"
    assert ProspectingBrief(brief=brief).to_wire() == {"brief": brief}
    assert ProspectingBrief(brief=brief, deliverable="accounts", goal="companies").to_wire() == {
        "brief": brief,
        "deliverable": "accounts",
        "goal": "companies",
    }
    with pytest.raises(ValidationError):
        ProspectingBrief.model_validate({"brief": brief, "deliverable": "people"})


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


def test_a_top_up_round_is_a_checkpoint(make_client: ClientFactory) -> None:
    replies = ["Raise the limit and run it", "Run a smaller round (40 companies)", "Finish with 60 found"]
    question = message_payload() | {
        "role": "agent",
        "kind": "question",
        "content": "60 of 100 companies had reachable people. Another round needs about 70 more matching companies.",
        "data": {"reason": "top_up", "suggested_replies": replies, "sample": []},
    }
    paused = payload("needs_input") | {"stop_reason": "top_up", "messages": [question]}
    with make_client(lambda request: httpx2.Response(200, json=paused)) as client:
        run = client.prospecting.wait(RUN_ID)
    assert run.stop_reason in CHECKPOINT_STOP_REASONS
    assert run.messages[-1].data == question["data"]


CONTACTS_REVIEW_REPLIES = ["Find emails", "Find more companies first", "Finish"]


def contacts_review_question() -> dict:
    return message_payload() | {
        "seq": 9,
        "role": "agent",
        "kind": "question",
        "content": "Checked 480 companies: 470 fit, 260 contacts matched the persona at 210 companies.",
        "data": {"reason": "contacts_review", "suggested_replies": CONTACTS_REVIEW_REPLIES, "sample": []},
    }


def test_wait_returns_contacts_review_with_open_stop_reason(make_client: ClientFactory) -> None:
    question = contacts_review_question()
    paused = payload("needs_input") | {"stop_reason": "contacts_review", "messages": [question]}
    with make_client(lambda request: httpx2.Response(200, json=paused)) as client:
        run = client.prospecting.wait(RUN_ID)
    assert (run.status, run.stop_reason) == ("needs_input", "contacts_review")
    assert run.stop_reason in CHECKPOINT_STOP_REASONS
    assert run.messages[-1].data == question["data"]


@pytest.mark.parametrize("reply", CONTACTS_REVIEW_REPLIES)
def test_contacts_review_reply_uses_message(make_client: ClientFactory, reply: str) -> None:
    bodies: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return httpx2.Response(202, json=message_payload())

    with make_client(handler) as client:
        client.prospecting.message(
            RUN_ID, ProspectingMessageRequest(text=reply, question_seq=9), idempotency_key="review-1"
        )
    assert bodies == [{"text": reply, "question_seq": 9}]


def test_message_without_question_seq_sends_the_same_body(make_client: ClientFactory) -> None:
    bodies: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return httpx2.Response(202, json=message_payload())

    with make_client(handler) as client:
        client.prospecting.message(RUN_ID, ProspectingMessageRequest(text="Find emails"), idempotency_key="k")
    assert bodies == [{"text": "Find emails"}]


def test_question_seq_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        ProspectingMessageRequest(text="Find emails", question_seq=0)


def test_a_run_reports_its_phase_provider_cost_and_shape(make_client: ClientFactory) -> None:
    phased = payload("running") | {
        "pipeline_phase": "people",
        "provider_cost_usd": 3.25,
        "brief": {"brief": "US logistics companies", "deliverable": "accounts", "goal": "companies"},
    }
    with make_client(lambda request: httpx2.Response(200, json=phased)) as client:
        run = client.prospecting.get(RUN_ID)
    assert (run.pipeline_phase, run.provider_cost_usd) == ("people", 3.25)
    assert (run.brief.deliverable, run.brief.goal) == ("accounts", "companies")


def test_a_run_from_before_phases_defaults_its_new_fields(make_client: ClientFactory) -> None:
    with make_client(lambda request: httpx2.Response(200, json=payload("running"))) as client:
        run = client.prospecting.get(RUN_ID)
    assert (run.pipeline_phase, run.provider_cost_usd) == (None, None)
    assert (run.brief.deliverable, run.brief.goal) == ("leads", "leads")


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


def test_approve_sends_a_segment_selection_only_when_given(make_client: ClientFactory) -> None:
    bodies: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return httpx2.Response(202, json=payload())

    with make_client(handler) as client:
        client.prospecting.approve(RUN_ID, ProspectingApproveRequest(plan_version=1))
        client.prospecting.approve(
            RUN_ID, ProspectingApproveRequest(plan_version=1, seed_segments=[1, 2], segment=True)
        )
    assert bodies == [{"plan_version": 1}, {"plan_version": 1, "seed_segments": [1, 2], "segment": True}]
    with pytest.raises(ValidationError):
        ProspectingApproveRequest(plan_version=1, seed_segments=[])


def test_a_seeded_brief_sends_and_reads_back_its_customers(make_client: ClientFactory) -> None:
    seen: list[httpx2.Request] = []
    customers = ["acme.com", "example.com"]

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        body = payload("drafting")
        return httpx2.Response(
            202,
            json=body | {"brief": body["brief"] | {"customer_domains": customers, "selected_seed_segments": [1]}},
        )

    with make_client(handler) as client:
        run = client.prospecting.start(
            ProspectingBrief(brief="Lookalikes of our customers and their CTOs", customer_domains=customers),
            idempotency_key="seeded",
        )
    assert json.loads(seen[0].content)["customer_domains"] == customers
    assert (run.brief.customer_domains, run.brief.selected_seed_segments) == (customers, [1])
    with pytest.raises(ValidationError):
        ProspectingBrief(brief="Lookalikes of our customers", customer_domains=["acme.com"] * 1001)


def test_answer_intake_posts_answers_with_key(make_client: ClientFactory) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(202, json=message_payload())

    with make_client(handler) as client:
        client.prospecting.answer_intake(
            RUN_ID, {"company_activity": IntakeAnswer(values=["sell"])}, idempotency_key="k"
        )
        message = client.prospecting.answer_intake(
            RUN_ID,
            {"company_activity": IntakeAnswer(values=["sell"]), "geography": IntakeAnswer(other="Ohio")},
            idempotency_key="k2",
            summary="Sellers in Ohio",
        )
    assert seen[0].url.path == f"/v1/prospecting/runs/{RUN_ID}/messages"
    assert seen[0].headers["Idempotency-Key"] == "k"
    assert json.loads(seen[0].content) == {"intake": {"company_activity": {"values": ["sell"]}}}
    assert json.loads(seen[1].content) == {
        "text": "Sellers in Ohio",
        "intake": {"company_activity": {"values": ["sell"]}, "geography": {"other": "Ohio"}},
    }
    assert message.seq == 8


async def test_async_answer_intake(make_async_client: AsyncClientFactory) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(202, json=message_payload())

    async with make_async_client(handler) as client:
        message = await client.prospecting.answer_intake(
            RUN_ID, {"list_size": IntakeAnswer(values=["1000"])}, idempotency_key="async-k"
        )
    assert seen[0].headers["Idempotency-Key"] == "async-k"
    assert json.loads(seen[0].content) == {"intake": {"list_size": {"values": ["1000"]}}}
    assert message.seq == 8


def test_intake_accepts_a_deliverable_answer() -> None:
    request = ProspectingMessageRequest(intake={"deliverable": IntakeAnswer(values=["accounts"])})
    assert request.to_wire() == {"intake": {"deliverable": {"values": ["accounts"]}}}


def test_answer_intake_rejects_unknown_key_and_long_other() -> None:
    with pytest.raises(ValidationError):
        ProspectingMessageRequest.model_validate({"intake": {"bogus": {"values": ["x"]}}})
    with pytest.raises(ValidationError):
        IntakeAnswer(other="x" * 201)


def test_message_request_needs_text_or_intake() -> None:
    with pytest.raises(ValidationError, match="send text or intake answers"):
        ProspectingMessageRequest()
    with pytest.raises(ValidationError, match="send text or intake answers"):
        ProspectingMessageRequest(intake={})


def test_answer_intake_rejects_empty_answers_before_sending(make_client: ClientFactory) -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(202, json=message_payload())

    with make_client(handler) as client, pytest.raises(ValidationError):
        client.prospecting.answer_intake(RUN_ID, {}, idempotency_key="k")
    assert seen == []
