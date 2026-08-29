import httpx2
import pytest

import discolike._transport as transport_module
from discolike import APIConnectionError
from discolike import RateLimitError
from discolike._transport import AsyncTransport
from discolike._transport import Transport
from discolike._transport import drop_none
from discolike_testkit import api_key_auth


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(transport_module.time, "sleep", sleeps.append)

    async def fake_async_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(transport_module.asyncio, "sleep", fake_async_sleep)
    return sleeps


def make_transport(handler) -> Transport:
    http = httpx2.Client(transport=httpx2.MockTransport(handler), base_url="https://api.test/v1")
    return Transport(
        api_key_auth("test-key"), base_url="https://api.test/v1", timeout=5.0, max_retries=2, http_client=http
    )


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

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.update(request.headers)
        return httpx2.Response(200, json={"ok": True})

    make_transport(handler).request("GET", "/usage")
    assert seen["x-discolike-key"] == "test-key"
    assert seen["user-agent"].startswith("discolike-python/")


def test_retries_on_503_then_succeeds(no_sleep) -> None:
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return httpx2.Response(503) if len(calls) < 3 else httpx2.Response(200, json={"ok": True})

    response = make_transport(handler).request("GET", "/usage")
    assert response.json() == {"ok": True}
    assert len(calls) == 3
    assert len(no_sleep) == 2


def test_429_exhausts_retries_then_raises(no_sleep) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(429, json={"detail": "slow down"}, headers={"Retry-After": "1"})

    with pytest.raises(RateLimitError):
        make_transport(handler).request("GET", "/usage")


def test_network_error_exhausts_then_raises(no_sleep) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("refused")

    with pytest.raises(APIConnectionError):
        make_transport(handler).request("GET", "/usage")


def test_400_does_not_retry() -> None:
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return httpx2.Response(400, json={"detail": "bad"})

    from discolike import ValidationError

    with pytest.raises(ValidationError):
        make_transport(handler).request("GET", "/usage")
    assert len(calls) == 1


def test_max_retries_zero_does_not_retry(no_sleep) -> None:
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return httpx2.Response(503, json={"detail": "unavailable"})

    from discolike import ServerError

    http = httpx2.Client(transport=httpx2.MockTransport(handler), base_url="https://api.test/v1")
    transport = Transport(
        api_key_auth("test-key"), base_url="https://api.test/v1", timeout=5.0, max_retries=0, http_client=http
    )
    with pytest.raises(ServerError):
        transport.request("GET", "/usage")
    assert len(calls) == 1
    assert no_sleep == []


async def test_async_transport_retries(no_sleep) -> None:
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return httpx2.Response(502) if len(calls) < 2 else httpx2.Response(200, json={"ok": True})

    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler), base_url="https://api.test/v1")
    transport = AsyncTransport(
        api_key_auth("test-key"), base_url="https://api.test/v1", timeout=5.0, max_retries=2, http_client=http
    )
    response = await transport.request("GET", "/usage")
    assert response.json() == {"ok": True}
    await transport.aclose()


def test_post_502_does_not_retry_and_raises_server_error(no_sleep) -> None:
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return httpx2.Response(502)

    from discolike import ServerError

    with pytest.raises(ServerError):
        make_transport(handler).request("POST", "/discogen/process")
    assert len(calls) == 1
    assert no_sleep == []


def test_post_429_is_still_retried(no_sleep) -> None:
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return httpx2.Response(429) if len(calls) < 2 else httpx2.Response(200, json={"ok": True})

    response = make_transport(handler).request("POST", "/discogen/process")
    assert response.json() == {"ok": True}
    assert len(calls) == 2
    assert len(no_sleep) == 1


def test_post_connect_error_is_retried_then_succeeds(no_sleep) -> None:
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        if len(calls) < 2:
            raise httpx2.ConnectError("refused")
        return httpx2.Response(200, json={"ok": True})

    response = make_transport(handler).request("POST", "/discogen/process")
    assert response.json() == {"ok": True}
    assert len(calls) == 2
    assert len(no_sleep) == 1


def test_post_read_timeout_raises_immediately_without_retry(no_sleep) -> None:
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        raise httpx2.ReadTimeout("timed out")

    with pytest.raises(APIConnectionError):
        make_transport(handler).request("POST", "/discogen/process")
    assert len(calls) == 1
    assert no_sleep == []


def test_delete_502_is_still_retried(no_sleep) -> None:
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return httpx2.Response(502) if len(calls) < 2 else httpx2.Response(200, json={"ok": True})

    response = make_transport(handler).request("DELETE", "/discogen/cancel/abc")
    assert response.json() == {"ok": True}
    assert len(calls) == 2


async def test_async_post_502_does_not_retry_and_raises_server_error(no_sleep) -> None:
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return httpx2.Response(502)

    from discolike import ServerError

    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler), base_url="https://api.test/v1")
    transport = AsyncTransport(
        api_key_auth("test-key"), base_url="https://api.test/v1", timeout=5.0, max_retries=2, http_client=http
    )
    with pytest.raises(ServerError):
        await transport.request("POST", "/discogen/process")
    assert len(calls) == 1
    assert no_sleep == []


async def test_async_post_connect_error_is_retried_then_succeeds(no_sleep) -> None:
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        if len(calls) < 2:
            raise httpx2.ConnectError("refused")
        return httpx2.Response(200, json={"ok": True})

    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler), base_url="https://api.test/v1")
    transport = AsyncTransport(
        api_key_auth("test-key"), base_url="https://api.test/v1", timeout=5.0, max_retries=2, http_client=http
    )
    response = await transport.request("POST", "/discogen/process")
    assert response.json() == {"ok": True}
    assert len(calls) == 2
    assert len(no_sleep) == 1


def test_byo_http_client_without_base_url_gets_base_url_set() -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["url"] = str(request.url)
        return httpx2.Response(200, json={"ok": True})

    http = httpx2.Client(transport=httpx2.MockTransport(handler))
    transport = Transport(
        api_key_auth("test-key"), base_url="https://api.test/v1", timeout=5.0, max_retries=0, http_client=http
    )
    transport.request("GET", "/usage")
    assert seen["url"] == "https://api.test/v1/usage"


def test_byo_http_client_with_base_url_is_left_alone() -> None:
    http = httpx2.Client(base_url="https://custom.example/v2")
    Transport(api_key_auth("test-key"), base_url="https://api.test/v1", timeout=5.0, max_retries=0, http_client=http)
    assert str(http.base_url) == "https://custom.example/v2/"


def test_with_timeout_overrides_request_timeout_and_leaves_base_alone() -> None:
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request.extensions["timeout"])
        return httpx2.Response(200, json={"ok": True})

    http = httpx2.Client(transport=httpx2.MockTransport(handler), base_url="https://api.test/v1", timeout=5.0)
    transport = Transport(
        api_key_auth("test-key"), base_url="https://api.test/v1", timeout=5.0, max_retries=0, http_client=http
    )
    transport.with_timeout(120.0).request("GET", "/usage")
    transport.request("GET", "/usage")

    assert seen[0]["read"] == 120.0
    assert seen[1]["read"] == 5.0
