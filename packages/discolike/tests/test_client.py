import time

import httpx2
import pytest

from discolike import AsyncDiscolike
from discolike import AuthenticationError
from discolike import Discolike
from discolike import OAuthCredential
from discolike._auth import DiscolikeAuth
from discolike._config import config_path
from discolike._config import load_credential
from discolike._config import save_credential
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


def test_client_accepts_injected_credential_and_does_not_persist_refresh(monkeypatch) -> None:
    credential = OAuthCredential(
        access_token="at", refresh_token="rt", expires_at=time.time() + 3600, client_id="c", token_endpoint="https://t"
    )
    seen: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request.headers["Authorization"])
        return httpx2.Response(200, json={"requests_mtd": 1})

    http = httpx2.Client(transport=httpx2.MockTransport(handler), base_url="https://api.test/v1")
    with Discolike(auth=credential, base_url="https://api.test/v1", http_client=http) as client:
        client.account.usage()
        auth = client._transport._client.auth
        assert isinstance(auth, DiscolikeAuth)
        assert auth.on_update is None
    assert seen == ["Bearer at"]
    assert not config_path().exists()


def test_client_from_config_oauth_persists_rotated_tokens() -> None:
    save_credential(
        OAuthCredential(
            access_token="stale", refresh_token="rt-1", expires_at=0.0, client_id="c", token_endpoint="https://t/token"
        )
    )

    def handler(request: httpx2.Request) -> httpx2.Response:
        if str(request.url) == "https://t/token":
            return httpx2.Response(200, json={"access_token": "fresh", "refresh_token": "rt-2", "expires_in": 3600})
        assert request.headers["Authorization"] == "Bearer fresh"
        return httpx2.Response(200, json={"requests_mtd": 1})

    http = httpx2.Client(transport=httpx2.MockTransport(handler), base_url="https://api.test/v1")
    with Discolike(base_url="https://api.test/v1", http_client=http) as client:
        assert client.account.usage().requests_mtd == 1
    stored = load_credential()
    assert isinstance(stored, OAuthCredential)
    assert (stored.access_token, stored.refresh_token) == ("fresh", "rt-2")


def test_with_options_view_shares_auth(make_client: ClientFactory) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"balance": 1})

    with make_client(handler) as client:
        assert client.with_options(timeout=1.0)._transport._client.auth is client._transport._client.auth


async def test_async_client_accepts_injected_credential() -> None:
    seen: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request.headers["Authorization"])
        return httpx2.Response(200, json={"requests_mtd": 1})

    credential = OAuthCredential(
        access_token="at", refresh_token="rt", expires_at=time.time() + 3600, client_id="c", token_endpoint="https://t"
    )
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler), base_url="https://api.test/v1")
    async with AsyncDiscolike(auth=credential, base_url="https://api.test/v1", http_client=http) as client:
        await client.account.usage()
    assert seen == ["Bearer at"]
