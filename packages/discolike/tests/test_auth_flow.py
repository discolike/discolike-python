import asyncio
import threading
import time

import httpx2
import pytest

from discolike import AuthenticationError
from discolike._auth import DiscolikeAuth
from discolike._credentials import ApiKeyCredential
from discolike._credentials import OAuthCredential
from discolike._oauth import REFRESH_LEEWAY_SECONDS

API = "https://api.test/v1"
TOKEN_ENDPOINT = "https://auth.test/oauth/2.1/token"
ONE_HOUR = 3600.0


def make_oauth(*, expires_in: float = ONE_HOUR, access_token: str = "at-1") -> OAuthCredential:
    return OAuthCredential(
        access_token=access_token,
        refresh_token="rt-1",
        expires_at=time.time() + expires_in,
        client_id="client-1",
        token_endpoint=TOKEN_ENDPOINT,
    )


class Server:
    """Mock API + token endpoint; counts refreshes and rejects any bearer it did not mint."""

    def __init__(self, *, valid_tokens: set[str], refresh_ok: bool = True) -> None:
        self.valid_tokens = valid_tokens
        self.refresh_ok = refresh_ok
        self.refreshes = 0
        self.bearers: list[str] = []
        self.token_calls: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        if str(request.url) == TOKEN_ENDPOINT:
            self.token_calls.append(request)
            if not self.refresh_ok:
                return httpx2.Response(400, json={"error": "invalid_grant", "error_description": "revoked"})
            self.refreshes += 1
            token = f"at-refreshed-{self.refreshes}"
            self.valid_tokens.add(token)
            return httpx2.Response(
                200, json={"access_token": token, "refresh_token": f"rt-{self.refreshes + 1}", "expires_in": 3600}
            )
        bearer = request.headers.get("Authorization", "")
        self.bearers.append(bearer)
        if bearer.removeprefix("Bearer ") in self.valid_tokens:
            return httpx2.Response(200, json={"ok": True})
        return httpx2.Response(401, json={"detail": "Invalid API Key or Session"})


def sync_client(auth: DiscolikeAuth, handler) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler), base_url=API, auth=auth)


def async_client(auth: DiscolikeAuth, handler) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(transport=httpx2.MockTransport(handler), base_url=API, auth=auth)


def test_api_key_credential_sets_header() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.update(request.headers)
        return httpx2.Response(200)

    sync_client(DiscolikeAuth(ApiKeyCredential(api_key="dk-1")), handler).get("/usage")
    assert seen["x-discolike-key"] == "dk-1"
    assert "authorization" not in seen


def test_oauth_credential_sets_bearer_without_refresh() -> None:
    server = Server(valid_tokens={"at-1"})
    response = sync_client(DiscolikeAuth(make_oauth()), server).get("/usage")
    assert response.status_code == 200
    assert server.refreshes == 0
    assert server.bearers[0] == "Bearer at-1"


def test_proactive_refresh_when_near_expiry() -> None:
    server = Server(valid_tokens={"at-1"})
    updates: list[OAuthCredential] = []
    auth = DiscolikeAuth(make_oauth(expires_in=REFRESH_LEEWAY_SECONDS / 2), on_update=updates.append)
    response = sync_client(auth, server).get("/usage")
    assert response.status_code == 200
    assert server.refreshes == 1
    assert server.bearers[0] == "Bearer at-refreshed-1"
    assert [update.access_token for update in updates] == ["at-refreshed-1"]
    assert updates[0].refresh_token == "rt-2"
    assert updates[0].client_id == "client-1"
    assert updates[0].token_endpoint == TOKEN_ENDPOINT
    assert auth.credential is updates[0]


def test_refresh_request_shape() -> None:
    server = Server(valid_tokens=set())
    sync_client(DiscolikeAuth(make_oauth(expires_in=0)), server).get("/usage")
    token_request = server.token_calls[0]
    assert token_request.method == "POST"
    assert token_request.headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert token_request.content.decode() == "grant_type=refresh_token&refresh_token=rt-1&client_id=client-1"


def test_401_triggers_refresh_and_single_replay() -> None:
    server = Server(valid_tokens=set())
    updates: list[OAuthCredential] = []
    response = sync_client(DiscolikeAuth(make_oauth(), on_update=updates.append), server).get("/usage")
    assert response.status_code == 200
    assert server.refreshes == 1
    assert server.bearers == ["Bearer at-1", "Bearer at-refreshed-1"]
    assert updates[0].access_token == "at-refreshed-1"


def test_second_401_after_replay_is_returned_not_retried() -> None:
    server = Server(valid_tokens=set())

    def reject_everything(request: httpx2.Request) -> httpx2.Response:
        response = server(request)
        if str(request.url) != TOKEN_ENDPOINT:
            return httpx2.Response(401, json={"detail": "Invalid API Key or Session"})
        return response

    response = sync_client(DiscolikeAuth(make_oauth()), reject_everything).get("/usage")
    assert response.status_code == 401
    assert server.refreshes == 1
    assert len(server.bearers) == 2


def test_refresh_failure_raises_authentication_error() -> None:
    server = Server(valid_tokens=set(), refresh_ok=False)
    with pytest.raises(AuthenticationError, match="discolike auth login"):
        sync_client(DiscolikeAuth(make_oauth(expires_in=0)), server).get("/usage")


def test_concurrent_requests_refresh_once() -> None:
    server = Server(valid_tokens=set())
    auth = DiscolikeAuth(make_oauth(expires_in=0))
    client = sync_client(auth, server)
    statuses: list[int] = []

    def worker() -> None:
        statuses.append(client.get("/usage").status_code)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert statuses == [200, 200, 200, 200]
    assert server.refreshes == 1


async def test_async_bearer_and_401_replay() -> None:
    server = Server(valid_tokens=set())
    updates: list[OAuthCredential] = []
    async with async_client(DiscolikeAuth(make_oauth(), on_update=updates.append), server) as client:
        response = await client.get("/usage")
    assert response.status_code == 200
    assert server.refreshes == 1
    assert server.bearers == ["Bearer at-1", "Bearer at-refreshed-1"]
    assert updates[0].access_token == "at-refreshed-1"


async def test_async_proactive_refresh_and_concurrency() -> None:
    server = Server(valid_tokens=set())
    async with async_client(DiscolikeAuth(make_oauth(expires_in=0)), server) as client:
        responses = await asyncio.gather(*(client.get("/usage") for _ in range(4)))
    assert [response.status_code for response in responses] == [200, 200, 200, 200]
    assert server.refreshes == 1


async def test_async_refresh_failure_raises_authentication_error() -> None:
    server = Server(valid_tokens=set(), refresh_ok=False)
    async with async_client(DiscolikeAuth(make_oauth(expires_in=0)), server) as client:
        with pytest.raises(AuthenticationError, match="discolike auth login"):
            await client.get("/usage")


async def test_async_api_key_header() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.update(request.headers)
        return httpx2.Response(200)

    async with async_client(DiscolikeAuth(ApiKeyCredential(api_key="dk-2")), handler) as client:
        await client.get("/usage")
    assert seen["x-discolike-key"] == "dk-2"
