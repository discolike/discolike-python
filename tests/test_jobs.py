import httpx
import pytest

import discolike._jobs as jobs_module
from discolike import JobFailedError
from discolike import JobTimeoutError
from discolike._jobs import FAMILY_DISCOGEN
from discolike._jobs import AsyncJob
from discolike._jobs import Job
from discolike._transport import AsyncTransport
from discolike._transport import Transport

BASE = "https://api.test/v1"


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(jobs_module.time, "sleep", lambda seconds: None)

    async def fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(jobs_module.asyncio, "sleep", fake_sleep)


def make_job(handler) -> Job:
    http = httpx.Client(transport=httpx.MockTransport(handler), base_url=BASE)
    transport = Transport("k", base_url=BASE, timeout=5.0, max_retries=0, http_client=http)
    return Job(transport, task_family=FAMILY_DISCOGEN, task_id="t-1")


def _status_sequence(payloads):
    state = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/discogen/status/t-1"
        payload = payloads[min(state["i"], len(payloads) - 1)]
        state["i"] += 1
        return httpx.Response(200, json=payload)

    return handler


def test_wait_polls_to_completion() -> None:
    handler = _status_sequence(
        [
            {"status": "in_progress", "progress": 10},
            {"status": "in_progress", "progress": 60},
            {"status": "completed", "progress": 100, "results": [{"domain": "a.com"}]},
        ]
    )
    final = make_job(handler).wait(timeout=60.0, poll_interval=1.0)
    assert final.status == "completed"
    assert final.results == [{"domain": "a.com"}]


def test_wait_failed_raises() -> None:
    handler = _status_sequence([{"status": "failed", "progress": 100, "result": "LLM exploded"}])
    with pytest.raises(JobFailedError, match="LLM exploded"):
        make_job(handler).wait(timeout=60.0)


def test_wait_timeout(monkeypatch) -> None:
    clock = {"now": 0.0}

    def mock_monotonic():
        clock["now"] += 100
        return clock["now"]

    monkeypatch.setattr(jobs_module.time, "monotonic", mock_monotonic)
    handler = _status_sequence([{"status": "in_progress", "progress": 1}])
    with pytest.raises(JobTimeoutError, match="t-1"):
        make_job(handler).wait(timeout=50.0)


def test_cancel_issues_delete() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(200, json={"status": "cancelling"})

    make_job(handler).cancel()
    assert (seen["method"], seen["path"]) == ("DELETE", "/v1/discogen/cancel/t-1")


async def test_async_job_wait() -> None:
    handler = _status_sequence(
        [{"status": "in_progress", "progress": 5}, {"status": "completed", "progress": 100, "results": []}]
    )
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url=BASE)
    transport = AsyncTransport("k", base_url=BASE, timeout=5.0, max_retries=0, http_client=http)
    final = await AsyncJob(transport, task_family=FAMILY_DISCOGEN, task_id="t-1").wait(timeout=60.0)
    assert final.status == "completed"
