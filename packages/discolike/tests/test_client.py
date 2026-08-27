import httpx2
import pytest

from discolike import AuthenticationError
from discolike import Discolike
from discolike_testkit import AsyncClientFactory
from discolike_testkit import ClientFactory


def test_client_requires_key() -> None:
    with pytest.raises(AuthenticationError):
        Discolike()


def test_client_reads_env_key(monkeypatch) -> None:
    monkeypatch.setenv("DISCOLIKE_API_KEY", "env-key")
    client = Discolike()
    client.close()


def test_usage(monkeypatch, make_client: ClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/v1/usage"
        return httpx2.Response(200, json={"requests_mtd": 42, "spend_mtd": 1.5})

    with make_client(handler) as client:
        usage = client.account.usage()
    assert usage.requests_mtd == 42


async def test_usage_async(make_async_client: AsyncClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"requests_mtd": 7})

    async with make_async_client(handler) as client:
        usage = await client.account.usage()
    assert usage.requests_mtd == 7


def test_route_metadata_stamped() -> None:
    from discolike.resources._base import get_discolike_route
    from discolike.resources.account import AccountResource

    assert get_discolike_route(AccountResource.usage) == ("GET", "/usage", True)


def test_with_options_timeout_applies_only_to_the_view(make_client: ClientFactory) -> None:
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request.extensions["timeout"])
        return httpx2.Response(200, json={"balance": 1})

    with make_client(handler) as client:
        client.with_options(timeout=120.0).account.usage()
        client.account.usage()

    assert seen[0]["read"] == 120.0
    assert seen[1]["read"] != 120.0


async def test_with_options_timeout_async(make_async_client: AsyncClientFactory) -> None:
    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request.extensions["timeout"])
        return httpx2.Response(200, json={"balance": 1})

    async with make_async_client(handler) as client:
        await client.with_options(timeout=90.0).account.usage()
        await client.account.usage()

    assert seen[0]["read"] == 90.0
    assert seen[1]["read"] != 90.0


def test_closing_a_with_options_view_leaves_parent_usable(make_client: ClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"balance": 1})

    with make_client(handler) as client:
        with client.with_options(timeout=30.0) as view:
            view.account.usage()
        client.account.usage()


async def test_closing_a_with_options_view_leaves_parent_usable_async(make_async_client: AsyncClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"balance": 1})

    async with make_async_client(handler) as client:
        async with client.with_options(timeout=30.0) as view:
            await view.account.usage()
        await client.account.usage()
