import httpx
import pytest

import discolike._transport as transport_module
from discolike import APIConnectionError, RateLimitError
from discolike._transport import AsyncTransport, Transport, drop_none


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(transport_module.time, "sleep", sleeps.append)

    async def fake_async_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(transport_module.asyncio, "sleep", fake_async_sleep)
    return sleeps


def make_transport(handler) -> Transport:
    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.test/v1")
    return Transport("test-key", base_url="https://api.test/v1", timeout=5.0, max_retries=2, http_client=http)


def test_drop_none() -> None:
    assert drop_none({"a": 1, "b": None, "c": ["x", "y"], "d": False, "e": 0, "f": ""}) == {
        "a": 1,
        "c": ["x", "y"],
        "d": False,
        "e": 0,
        "f": "",
    }
    assert drop_none(None) == {}


def test_auth_and_user_agent_headers() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json={"ok": True})

    make_transport(handler).request("GET", "/usage")
    assert seen["x-discolike-key"] == "test-key"
    assert seen["user-agent"].startswith("discolike-python/")


def test_retries_on_503_then_succeeds(no_sleep) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, json={"ok": True})

    response = make_transport(handler).request("GET", "/usage")
    assert response.json() == {"ok": True}
    assert len(calls) == 3
    assert len(no_sleep) == 2


def test_429_exhausts_retries_then_raises(no_sleep) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"detail": "slow down"}, headers={"Retry-After": "1"})

    with pytest.raises(RateLimitError):
        make_transport(handler).request("GET", "/usage")


def test_network_error_exhausts_then_raises(no_sleep) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(APIConnectionError):
        make_transport(handler).request("GET", "/usage")


def test_400_does_not_retry() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400, json={"detail": "bad"})

    from discolike import ValidationError

    with pytest.raises(ValidationError):
        make_transport(handler).request("GET", "/usage")
    assert len(calls) == 1


def test_max_retries_zero_does_not_retry(no_sleep) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503, json={"detail": "unavailable"})

    from discolike import ServerError

    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.test/v1")
    transport = Transport("test-key", base_url="https://api.test/v1", timeout=5.0, max_retries=0, http_client=http)
    with pytest.raises(ServerError):
        transport.request("GET", "/usage")
    assert len(calls) == 1
    assert no_sleep == []


async def test_async_transport_retries(no_sleep) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(502) if len(calls) < 2 else httpx.Response(200, json={"ok": True})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.test/v1")
    transport = AsyncTransport("test-key", base_url="https://api.test/v1", timeout=5.0, max_retries=2, http_client=http)
    response = await transport.request("GET", "/usage")
    assert response.json() == {"ok": True}
    await transport.aclose()
