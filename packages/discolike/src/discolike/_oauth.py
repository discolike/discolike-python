from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx2
from authlib.common.security import generate_token
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.integrations.httpx_client import OAuth2Client
from authlib.oauth2.client import OAuth2Client as BaseOAuth2Client

from discolike._credentials import OAuthCredential
from discolike._exceptions import AuthenticationError

OAUTH_SCOPE = "offline_access"
REFRESH_LEEWAY_SECONDS = 60.0
TOKEN_TIMEOUT_SECONDS = 30.0
CLIENT_NAME = "discolike-cli"
METADATA_PATH = "/.well-known/oauth-authorization-server"
GRANT_TYPES = ["authorization_code", "refresh_token"]
RESPONSE_TYPES = ["code"]
PKCE_METHOD = "S256"
PKCE_VERIFIER_LENGTH = 64
PUBLIC_CLIENT_AUTH = "none"
TOKEN_KEYS = frozenset({"access_token", "refresh_token", "id_token"})
SESSION_EXPIRED_MESSAGE = "OAuth session expired; run `discolike auth login`"


class OAuthError(AuthenticationError):
    """An RFC 6749 error body from the authorization server; `error` is its machine-readable code."""

    def __init__(
        self,
        message: str,
        *,
        error: str,
        status_code: int | None = None,
        payload: Any = None,  # noqa: ANN401 -- decoded JSON body, shape is server-defined
    ) -> None:
        super().__init__(message, status_code=status_code, payload=payload)
        self.error = error


@dataclass(frozen=True)
class AuthServerMetadata:
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str
    issuer: str


def _payload(response: httpx2.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise AuthenticationError(
            f"OAuth server returned a non-JSON response (HTTP {response.status_code})", status_code=response.status_code
        ) from exc
    if isinstance(payload, dict) and "error" in payload:
        description = payload.get("error_description")
        error = str(payload["error"])
        message = f"{error}: {description}" if description else error
        raise OAuthError(message, error=error, status_code=response.status_code, payload=payload)
    if response.status_code >= 400 or not isinstance(payload, dict):
        raise AuthenticationError(
            f"OAuth server returned HTTP {response.status_code}", status_code=response.status_code, payload=payload
        )
    return payload


def _require(payload: dict[str, Any], key: str) -> str:
    if key not in payload:
        raise AuthenticationError(f"OAuth server response is missing `{key}`", payload=payload)
    return str(payload[key])


class _StrictTokenParsing(BaseOAuth2Client):
    """Authlib swallows HTTP status and non-`error` failures; raise the SDK's exceptions before it parses."""

    def parse_response_token(self, resp: httpx2.Response) -> dict[str, Any]:
        _payload(resp)
        return super().parse_response_token(resp)


class TokenClient(_StrictTokenParsing, OAuth2Client):
    pass


class AsyncTokenClient(_StrictTokenParsing, AsyncOAuth2Client):
    pass


def _client_kwargs(
    *,
    client_id: str,
    redirect_uri: str | None = None,
    scope: str | None = None,
    transport: httpx2.BaseTransport | httpx2.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "code_challenge_method": PKCE_METHOD,
        "token_endpoint_auth_method": PUBLIC_CLIENT_AUTH,
        "timeout": TOKEN_TIMEOUT_SECONDS,
    }
    if transport is not None:
        kwargs["transport"] = transport
    return kwargs


def _credential_from_token(
    token: dict[str, Any],
    *,
    client_id: str,
    token_endpoint: str,
    resource: str | None,
    fallback_refresh_token: str | None,
) -> OAuthCredential:
    # Exceptions raised here may be logged by SDK consumers; never attach live tokens to them.
    safe_payload = {key: value for key, value in token.items() if key not in TOKEN_KEYS}
    refresh_token = token.get("refresh_token") or fallback_refresh_token
    if not refresh_token:
        raise AuthenticationError("OAuth token response has no `refresh_token`", payload=safe_payload)
    if "access_token" not in token:
        raise AuthenticationError("OAuth server response is missing `access_token`", payload=safe_payload)
    if "expires_at" not in token:
        raise AuthenticationError("OAuth server response is missing `expires_in`", payload=safe_payload)
    return OAuthCredential(
        access_token=str(token["access_token"]),
        refresh_token=str(refresh_token),
        expires_at=float(token["expires_at"]),
        client_id=client_id,
        token_endpoint=token_endpoint,
        resource=resource,
    )


def _refresh_kwargs(credential: OAuthCredential) -> dict[str, Any]:
    """Resend the resource the token was issued for; credentials stored before 0.3.3 have none."""
    kwargs: dict[str, Any] = {"refresh_token": credential.refresh_token}
    if credential.resource:
        kwargs["resource"] = credential.resource
    return kwargs


def discover(base_url: str, *, client: httpx2.Client) -> AuthServerMetadata:
    payload = _payload(client.get(base_url.rstrip("/") + METADATA_PATH))
    return AuthServerMetadata(
        authorization_endpoint=_require(payload, "authorization_endpoint"),
        token_endpoint=_require(payload, "token_endpoint"),
        registration_endpoint=_require(payload, "registration_endpoint"),
        issuer=_require(payload, "issuer"),
    )


def register_client(metadata: AuthServerMetadata, *, redirect_uris: list[str], client: httpx2.Client) -> str:
    body = {
        "client_name": CLIENT_NAME,
        "redirect_uris": redirect_uris,
        "grant_types": GRANT_TYPES,
        "response_types": RESPONSE_TYPES,
        "token_endpoint_auth_method": PUBLIC_CLIENT_AUTH,
    }
    return _require(_payload(client.post(metadata.registration_endpoint, json=body)), "client_id")


def build_authorization_url(
    metadata: AuthServerMetadata, *, client_id: str, redirect_uri: str, state: str, resource: str
) -> tuple[str, str]:
    """Returns the URL to open and the PKCE code verifier to present at `exchange_code`."""
    code_verifier = generate_token(PKCE_VERIFIER_LENGTH)
    with TokenClient(**_client_kwargs(client_id=client_id, redirect_uri=redirect_uri, scope=OAUTH_SCOPE)) as client:
        url, _ = client.create_authorization_url(
            metadata.authorization_endpoint, state=state, code_verifier=code_verifier, resource=resource
        )
    return str(url), code_verifier


def exchange_code(
    metadata: AuthServerMetadata,
    *,
    client_id: str,
    code: str,
    code_verifier: str,
    redirect_uri: str,
    resource: str,
    transport: httpx2.BaseTransport | None = None,
) -> OAuthCredential:
    kwargs = _client_kwargs(client_id=client_id, redirect_uri=redirect_uri, scope=OAUTH_SCOPE, transport=transport)
    with TokenClient(**kwargs) as client:
        token = client.fetch_token(metadata.token_endpoint, code=code, code_verifier=code_verifier, resource=resource)
    return _credential_from_token(
        token,
        client_id=client_id,
        token_endpoint=metadata.token_endpoint,
        resource=resource,
        fallback_refresh_token=None,
    )


def refresh(
    credential: OAuthCredential, *, transport: httpx2.BaseTransport | httpx2.AsyncBaseTransport | None = None
) -> OAuthCredential:
    """Rotates the tokens; any failure means the session is gone and the user must log in again."""
    try:
        with TokenClient(**_client_kwargs(client_id=credential.client_id, transport=transport)) as client:
            token = client.refresh_token(credential.token_endpoint, **_refresh_kwargs(credential))
        return _credential_from_token(
            token,
            client_id=credential.client_id,
            token_endpoint=credential.token_endpoint,
            resource=credential.resource,
            fallback_refresh_token=credential.refresh_token,
        )
    except AuthenticationError as exc:
        raise AuthenticationError(SESSION_EXPIRED_MESSAGE, status_code=exc.status_code, payload=exc.payload) from exc


async def refresh_async(
    credential: OAuthCredential, *, transport: httpx2.BaseTransport | httpx2.AsyncBaseTransport | None = None
) -> OAuthCredential:
    try:
        async with AsyncTokenClient(**_client_kwargs(client_id=credential.client_id, transport=transport)) as client:
            token = await client.refresh_token(credential.token_endpoint, **_refresh_kwargs(credential))
        return _credential_from_token(
            token,
            client_id=credential.client_id,
            token_endpoint=credential.token_endpoint,
            resource=credential.resource,
            fallback_refresh_token=credential.refresh_token,
        )
    except AuthenticationError as exc:
        raise AuthenticationError(SESSION_EXPIRED_MESSAGE, status_code=exc.status_code, payload=exc.payload) from exc
