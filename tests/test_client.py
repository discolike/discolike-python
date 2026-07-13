import httpx
import pytest

from conftest import make_async_client, make_client
from discolike import AuthenticationError, Discolike


def test_client_requires_key() -> None:
    with pytest.raises(AuthenticationError):
        Discolike()


def test_client_reads_env_key(monkeypatch) -> None:
    monkeypatch.setenv("DISCOLIKE_API_KEY", "env-key")
    client = Discolike()
    client.close()


def test_usage(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/usage"
        return httpx.Response(200, json={"requests_mtd": 42, "spend_mtd": 1.5})

    with make_client(handler) as client:
        usage = client.account.usage()
    assert usage.requests_mtd == 42


async def test_usage_async() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"requests_mtd": 7})

    async with make_async_client(handler) as client:
        usage = await client.account.usage()
    assert usage.requests_mtd == 7


def test_route_metadata_stamped() -> None:
    from discolike.resources.account import AccountResource

    assert AccountResource.usage.__discolike_route__ == ("GET", "/usage", True)  # ty: ignore[unresolved-attribute]
