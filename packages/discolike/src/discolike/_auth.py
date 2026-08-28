from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncGenerator
from collections.abc import Callable
from collections.abc import Generator
from typing import cast

import httpx2

from discolike._credentials import ApiKeyCredential
from discolike._credentials import Credential
from discolike._credentials import OAuthCredential
from discolike._exceptions import AuthenticationError
from discolike._oauth import REFRESH_LEEWAY_SECONDS
from discolike._oauth import SESSION_EXPIRED_MESSAGE
from discolike._oauth import parse_refresh_response
from discolike._oauth import refresh_request

API_KEY_HEADER = "X-discolike-key"
UNAUTHORIZED = 401


def _set_bearer(request: httpx2.Request, credential: OAuthCredential) -> None:
    request.headers["Authorization"] = f"Bearer {credential.access_token}"


class DiscolikeAuth(httpx2.Auth):
    """Sends the API key header, or a bearer token that is refreshed before expiry and once after a 401.

    Refreshes go through the same client as the request they precede, so tests drive them via ``MockTransport``.
    """

    requires_response_body = False

    def __init__(self, credential: Credential, *, on_update: Callable[[OAuthCredential], None] | None = None) -> None:
        self._credential = credential
        self.on_update = on_update
        self._lock = threading.Lock()
        self._async_lock = asyncio.Lock()

    @property
    def credential(self) -> Credential:
        return self._credential

    def _latest(self, credential: OAuthCredential) -> OAuthCredential:
        return cast(OAuthCredential, self._credential) if self._credential is not credential else credential

    def _store(self, response: httpx2.Response, *, credential: OAuthCredential) -> OAuthCredential:
        try:
            rotated = parse_refresh_response(response, credential=credential)
        except AuthenticationError as exc:
            raise AuthenticationError(
                SESSION_EXPIRED_MESSAGE, status_code=exc.status_code, payload=exc.payload
            ) from exc
        self._credential = rotated
        if self.on_update is not None:
            self.on_update(rotated)
        return rotated

    def sync_auth_flow(self, request: httpx2.Request) -> Generator[httpx2.Request, httpx2.Response, None]:
        credential = self._credential
        if isinstance(credential, ApiKeyCredential):
            request.headers[API_KEY_HEADER] = credential.api_key
            yield request
            return
        with self._lock:
            credential = self._latest(credential)
            if credential.expires_within(REFRESH_LEEWAY_SECONDS):
                credential = yield from self._sync_refresh(credential)
        _set_bearer(request, credential)
        response = yield request
        if response.status_code != UNAUTHORIZED:
            return
        with self._lock:
            latest = self._latest(credential)
            if latest is credential:
                latest = yield from self._sync_refresh(credential)
        _set_bearer(request, latest)
        yield request

    def _sync_refresh(self, credential: OAuthCredential) -> Generator[httpx2.Request, httpx2.Response, OAuthCredential]:
        response = yield refresh_request(credential)
        response.read()
        return self._store(response, credential=credential)

    async def async_auth_flow(self, request: httpx2.Request) -> AsyncGenerator[httpx2.Request, httpx2.Response]:
        credential = self._credential
        if isinstance(credential, ApiKeyCredential):
            request.headers[API_KEY_HEADER] = credential.api_key
            yield request
            return
        async with self._async_lock:
            credential = self._latest(credential)
            if credential.expires_within(REFRESH_LEEWAY_SECONDS):
                response = yield refresh_request(credential)
                await response.aread()
                credential = self._store(response, credential=credential)
        _set_bearer(request, credential)
        response = yield request
        if response.status_code != UNAUTHORIZED:
            return
        async with self._async_lock:
            latest = self._latest(credential)
            if latest is credential:
                response = yield refresh_request(credential)
                await response.aread()
                latest = self._store(response, credential=credential)
        _set_bearer(request, latest)
        yield request
