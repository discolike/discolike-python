from __future__ import annotations

import json
from uuid import UUID

import httpx2
import pytest

import discolike.resources.prospecting as module
from discolike import JobTimeoutError
from discolike.requests import ProspectingBrief
from discolike.requests import ProspectingGetParams
from discolike_testkit import AsyncClientFactory
from discolike_testkit import ClientFactory

RUN_ID = "00000000-0000-0000-0000-000000000001"


def payload(status: str = "queued") -> dict:
    return {"run_id": RUN_ID, "status": status, "max_actions": 24, "companies": [{"domain": "example.com"}]}


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
        client.prospecting.wait(RUN_ID, timeout=1)
    assert seen == ["GET"]


@pytest.mark.parametrize("key", ["", " ", "a" * 129])
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
