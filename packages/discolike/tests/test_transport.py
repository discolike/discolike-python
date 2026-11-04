import warnings
from concurrent.futures import ThreadPoolExecutor

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
    monkeypatch.setattr(transport_module, "_warned_endpoints", set())
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


@pytest.mark.parametrize("use_async", [False, True])
async def test_deprecation_once_per_method_and_template_across_clients(use_async) -> None:
    headers = {
        "Deprecation": "@1793664000",
        "Sunset": "Wed, 03 Nov 2027 00:00:00 GMT",
        "Link": '<https://api.test/migration>; rel="deprecation"',
    }

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"ok": True}, headers=headers)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        for path in ("/email/jobs/123", "/email/jobs/456", "/email/jobs/opaque-job"):
            if use_async:
                http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler), base_url="https://api.test/v1")
                transport = AsyncTransport(
                    api_key_auth("test-key"),
                    base_url="https://api.test/v1",
                    timeout=5.0,
                    max_retries=0,
                    http_client=http,
                )
                await transport.request("GET", path)
                await transport.aclose()
            else:
                transport = make_transport(handler)
                transport.with_timeout(1.0).request("GET", path)
                transport.close()
        assert len(caught) == 1
        transport = make_transport(handler)
        transport.request("GET", "/email/jobs/789")
        transport.request("POST", "/email/jobs/123")
        transport.request("GET", "/usage")
        transport.close()
        assert len(caught) == 3
    message = str(caught[0].message)
    assert "GET /email/jobs/{job_id}" in message
    for name, value in headers.items():
        assert f"{name}: {value}" in message


@pytest.mark.parametrize("use_async", [False, True])
@pytest.mark.parametrize("deprecation", [None, "", "not-a-date; ???", "@999999999999999999999999999999"])
async def test_deprecation_missing_or_malformed_headers(use_async, deprecation) -> None:
    headers = {"Sunset": "not a date", "Link": "<broken"}
    if deprecation is not None:
        headers["Deprecation"] = deprecation

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"ok": True}, headers=headers)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        if use_async:
            http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler), base_url="https://api.test/v1")
            transport = AsyncTransport(
                api_key_auth("test-key"), base_url="https://api.test/v1", timeout=5.0, max_retries=0, http_client=http
            )
            response = await transport.request("GET", "/usage")
            await transport.aclose()
        else:
            transport = make_transport(handler)
            response = transport.request("GET", "/usage")
            transport.close()
    assert response.json() == {"ok": True}
    assert len(caught) == (0 if deprecation is None else 1)
    if caught:
        assert "Sunset: not a date" in str(caught[0].message)
        assert "Link: <broken" in str(caught[0].message)


def test_deprecation_thread_safe() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={}, headers={"Deprecation": "true"})

    def request(job_id: int) -> None:
        transport = make_transport(handler)
        try:
            transport.request("GET", f"/email/jobs/{job_id}")
        finally:
            transport.close()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(request, range(32)))
    assert len(caught) == 1


@pytest.mark.parametrize(
    "paths",
    [
        ("/future/123", "/future/456"),
        ("/future/123e4567-e89b-12d3-a456-426614174000", "/future/123e4567-e89b-12d3-a456-426614174001"),
        ("/email/batch/first/results?offset=0", "/email/batch/second/results?offset=1"),
    ],
)
def test_deprecation_normalizes_identifiers_and_query_strings(paths) -> None:
    transport = make_transport(lambda request: httpx2.Response(200, json={}, headers={"Deprecation": "true"}))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        for path in paths:
            transport.request("GET", path)
    transport.close()
    assert len(caught) == 1
