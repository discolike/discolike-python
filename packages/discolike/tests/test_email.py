from __future__ import annotations

import json

import httpx
import pytest

import discolike._jobs as jobs_module
from conftest import make_async_client
from conftest import make_client
from discolike import JobFailedError
from discolike.resources.email import AsyncEmailBatch
from discolike.resources.email import AsyncEmailJob
from discolike.resources.email import EmailBatch
from discolike.resources.email import EmailJob
from discolike.resources.email import EnumerationOutput
from discolike.resources.email import ValidationOutput


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(jobs_module.time, "sleep", lambda seconds: None)

    async def fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(jobs_module.asyncio, "sleep", fake_sleep)


def _results_sequence(payloads):
    state = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.startswith("/v1/email/batch/")
        assert request.url.path.endswith("/results")
        payload = payloads[min(state["i"], len(payloads) - 1)]
        state["i"] += 1
        return httpx.Response(200, json=payload)

    return handler


def test_find_batch_posts_and_returns_batch() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx.Response(202, json={"batch_id": "b-1", "job_ids": ["j-1", "j-2"], "total": 2})

    with make_client(handler) as client:
        batch = client.email.find_batch(
            contacts=[
                {"first_name": "Ada", "last_name": "Lovelace", "domain": "acme.com"},
                {"first_name": "Alan", "last_name": "Turing", "domain": "acme.com"},
            ]
        )

    assert seen["path"] == "/v1/email/find/batch"
    assert seen["method"] == "POST"
    assert seen["body"] == {
        "requests": [
            {"first_name": "Ada", "last_name": "Lovelace", "domain": "acme.com"},
            {"first_name": "Alan", "last_name": "Turing", "domain": "acme.com"},
        ]
    }
    assert isinstance(batch, EmailBatch)
    assert batch.batch_id == "b-1"
    assert batch.kind == "find"


def test_verify_batch_results_polls_and_decodes_validation_output() -> None:
    handler = _results_sequence(
        [
            {
                "batch_id": "b-2",
                "total": 1,
                "completed": 0,
                "failed": 0,
                "results": [{"job_id": "j-3", "status": "queued", "result": None, "error": None}],
            },
            {
                "batch_id": "b-2",
                "total": 1,
                "completed": 0,
                "failed": 0,
                "results": [{"job_id": "j-3", "status": "processing", "result": None, "error": None}],
            },
            {
                "batch_id": "b-2",
                "total": 1,
                "completed": 1,
                "failed": 0,
                "results": [
                    {
                        "job_id": "j-3",
                        "status": "completed",
                        "result": {
                            "email": "ada@acme.com",
                            "status": "safe",
                            "is_deliverable": True,
                            "is_catch_all": False,
                            "smtp_code": 250,
                            "attempts": 1,
                            "duration_ms": 42,
                            "reason": "deliverable",
                        },
                        "error": None,
                    }
                ],
            },
        ]
    )

    with make_client(handler) as client:
        batch = client.email.batch("b-2", kind="verify")
        results = batch.results(timeout=60.0, poll_interval=1.0)

    assert results.batch_id == "b-2"
    assert results.total == 1
    assert results.completed == 1
    item = results.results[0]
    assert item.job_id == "j-3"
    assert item.status == "completed"
    assert isinstance(item.result, ValidationOutput)
    assert item.result.status == "safe"
    assert item.result.is_deliverable is True
    assert item.result.smtp_code == 250
    assert item.result.reason == "deliverable"


def test_find_batch_results_decodes_enumeration_output_and_failed_item() -> None:
    handler = _results_sequence(
        [
            {
                "batch_id": "b-1",
                "total": 2,
                "completed": 1,
                "failed": 1,
                "results": [
                    {
                        "job_id": "j-1",
                        "status": "completed",
                        "result": {
                            "first_name": "Ada",
                            "last_name": "Lovelace",
                            "domain": "acme.com",
                            "status": "found",
                            "result": {
                                "email": "ada@acme.com",
                                "pattern": "{first}",
                                "tier": 1,
                                "smtp_code": 250,
                                "valid": True,
                            },
                            "is_catch_all": False,
                            "attempts": 1,
                            "duration_ms": 88,
                        },
                        "error": None,
                    },
                    {
                        "job_id": "j-2",
                        "status": "failed",
                        "result": None,
                        "error": "smtp timeout",
                    },
                ],
            }
        ]
    )

    with make_client(handler) as client:
        results = client.email.batch("b-1", kind="find").results(timeout=60.0, poll_interval=1.0)

    assert results.total == 2
    assert results.failed == 1
    found = next(item for item in results.results if item.job_id == "j-1")
    failed = next(item for item in results.results if item.job_id == "j-2")
    assert isinstance(found.result, EnumerationOutput)
    assert found.result.status == "found"
    assert found.result.result is not None
    assert found.result.result.email == "ada@acme.com"
    assert found.result.result.tier == 1
    assert failed.status == "failed"
    assert failed.result is None
    assert failed.error == "smtp timeout"


def test_find_posts_and_job_wait_polls_jobs_endpoint() -> None:
    seen = {}
    state = {"i": 0}
    poll_payloads = [
        {"job_id": "j-9", "status": "queued", "result": None, "error": None},
        {"job_id": "j-9", "status": "processing", "result": None, "error": None},
        {
            "job_id": "j-9",
            "status": "completed",
            "result": {
                "first_name": "Grace",
                "last_name": "Hopper",
                "domain": "navy.mil",
                "status": "found",
                "result": {
                    "email": "grace@navy.mil",
                    "pattern": "{first}",
                    "tier": 1,
                    "smtp_code": 250,
                    "valid": True,
                },
                "is_catch_all": False,
                "attempts": 2,
                "duration_ms": 120,
            },
            "error": None,
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            seen["path"] = request.url.path
            seen["body"] = json.loads(request.content)
            return httpx.Response(202, json={"job_id": "j-9", "status": "queued"})
        assert request.url.path == "/v1/email/jobs/j-9"
        payload = poll_payloads[min(state["i"], len(poll_payloads) - 1)]
        state["i"] += 1
        return httpx.Response(200, json=payload)

    with make_client(handler) as client:
        job = client.email.find(first_name="Grace", last_name="Hopper", domain="navy.mil")
        assert isinstance(job, EmailJob)
        assert job.job_id == "j-9"
        output = job.wait(timeout=60.0, poll_interval=1.0)

    assert seen["path"] == "/v1/email/find"
    assert seen["body"] == {"first_name": "Grace", "last_name": "Hopper", "domain": "navy.mil"}
    assert isinstance(output, EnumerationOutput)
    assert output.status == "found"
    assert output.result is not None
    assert output.result.email == "grace@navy.mil"


def test_find_wait_raises_on_failed_job() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(202, json={"job_id": "j-x", "status": "queued"})
        return httpx.Response(200, json={"job_id": "j-x", "status": "failed", "result": None, "error": "boom"})

    with make_client(handler) as client:
        job = client.email.find(first_name="No", last_name="One", domain="void.dev")
        with pytest.raises(JobFailedError, match="boom"):
            job.wait(timeout=60.0)


def test_job_reattaches_without_http_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("job()/batch() must not perform an HTTP request")

    with make_client(handler) as client:
        job = client.email.job("j-existing")
        batch = client.email.batch("b-existing", kind="verify")

    assert isinstance(job, EmailJob)
    assert job.job_id == "j-existing"
    assert job.kind == "find"
    assert isinstance(batch, EmailBatch)
    assert batch.kind == "verify"


async def test_find_batch_async_returns_batch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(202, json={"batch_id": "b-async", "job_ids": ["j-a"], "total": 1})

    async with make_async_client(handler) as client:
        batch = await client.email.find_batch(
            contacts=[{"first_name": "Ada", "last_name": "Lovelace", "domain": "acme.com"}]
        )

    assert isinstance(batch, AsyncEmailBatch)
    assert batch.batch_id == "b-async"
    assert batch.kind == "find"


async def test_verify_batch_async_results_decodes() -> None:
    handler = _results_sequence(
        [
            {
                "batch_id": "b-async2",
                "total": 1,
                "completed": 0,
                "failed": 0,
                "results": [{"job_id": "j-b", "status": "processing", "result": None, "error": None}],
            },
            {
                "batch_id": "b-async2",
                "total": 1,
                "completed": 1,
                "failed": 0,
                "results": [
                    {
                        "job_id": "j-b",
                        "status": "completed",
                        "result": {
                            "email": "risky@acme.com",
                            "status": "risky",
                            "is_deliverable": False,
                            "is_catch_all": True,
                            "smtp_code": None,
                            "attempts": 1,
                            "duration_ms": 10,
                        },
                        "error": None,
                    }
                ],
            },
        ]
    )

    async with make_async_client(handler) as client:
        batch = client.email.batch("b-async2", kind="verify")
        results = await batch.results(timeout=60.0, poll_interval=1.0)

    item = results.results[0]
    assert isinstance(item.result, ValidationOutput)
    assert item.result.status == "risky"
    assert item.result.is_catch_all is True
    assert item.result.reason is None


async def test_find_async_job_wait() -> None:
    state = {"i": 0}
    poll_payloads = [
        {"job_id": "j-async", "status": "processing", "result": None, "error": None},
        {
            "job_id": "j-async",
            "status": "completed",
            "result": {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "domain": "acme.com",
                "status": "found",
                "result": {"email": "ada@acme.com", "pattern": "{first}", "tier": 2, "smtp_code": 250, "valid": True},
                "is_catch_all": False,
                "attempts": 1,
                "duration_ms": 30,
            },
            "error": None,
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(202, json={"job_id": "j-async", "status": "queued"})
        payload = poll_payloads[min(state["i"], len(poll_payloads) - 1)]
        state["i"] += 1
        return httpx.Response(200, json=payload)

    async with make_async_client(handler) as client:
        job = await client.email.find(first_name="Ada", last_name="Lovelace", domain="acme.com")
        assert isinstance(job, AsyncEmailJob)
        output = await job.wait(timeout=60.0, poll_interval=1.0)

    assert isinstance(output, EnumerationOutput)
    assert output.result is not None
    assert output.result.tier == 2


def test_route_metadata_stamped() -> None:
    from discolike.resources._base import get_discolike_route
    from discolike.resources.email import EmailResource

    assert get_discolike_route(EmailResource.find) == ("POST", "/email/find", True, ())
    assert get_discolike_route(EmailResource.find_batch) == ("POST", "/email/find/batch", True, ("contacts",))
    assert get_discolike_route(EmailResource.job) is None
    assert get_discolike_route(EmailResource.batch) is None


def test_verify_batch_is_not_part_of_the_sdk_surface() -> None:
    """Submission of arbitrary addresses is app-internal; the SDK must not offer it."""
    from discolike.resources.email import AsyncEmailResource
    from discolike.resources.email import EmailResource

    assert not hasattr(EmailResource, "verify_batch")
    assert not hasattr(AsyncEmailResource, "verify_batch")


def test_batch_can_still_re_attach_to_a_verify_batch() -> None:
    """`verify_batch` is gone, but results polling stays public — so a batch id
    the DiscoLike app created is still the only way to reach a `ValidationOutput`,
    and re-attaching to one must round-trip end to end."""
    handler = _results_sequence(
        [
            {
                "batch_id": "b-9",
                "total": 1,
                "completed": 1,
                "failed": 0,
                "results": [
                    {
                        "job_id": "j-9",
                        "status": "completed",
                        "result": {
                            "email": "ada@acme.com",
                            "status": "invalid",
                            "is_deliverable": False,
                            "is_catch_all": False,
                            "reason": "no_mailbox",
                        },
                        "error": None,
                    }
                ],
            }
        ]
    )

    with make_client(handler) as client:
        batch = client.email.batch("b-9", kind="verify")
        results = batch.results(timeout=60.0, poll_interval=1.0)

    assert isinstance(batch, EmailBatch)
    assert batch.batch_id == "b-9"
    assert batch.kind == "verify"
    item = results.results[0]
    assert isinstance(item.result, ValidationOutput)
    assert item.result.status == "invalid"
    assert item.result.reason == "no_mailbox"
