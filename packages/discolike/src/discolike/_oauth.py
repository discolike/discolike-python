from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx2

from discolike._credentials import OAuthCredential
from discolike._exceptions import AuthenticationError

OAUTH_SCOPE = "offline_access"
REFRESH_LEEWAY_SECONDS = 60.0
CLIENT_NAME = "discolike-cli"
METADATA_PATH = "/.well-known/oauth-authorization-server"
GRANT_TYPES = ["authorization_code", "refresh_token"]
RESPONSE_TYPES = ["code"]
PKCE_METHOD = "S256"
PKCE_VERIFIER_BYTES = 32
TOKEN_HEADERS = {"Accept": "application/json"}
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


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def pkce_pair() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(PKCE_VERIFIER_BYTES))
    return verifier, _b64url(hashlib.sha256(verifier.encode("ascii")).digest())


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


def _credential_from_token_payload(
    payload: dict[str, Any], *, client_id: str, token_endpoint: str, fallback_refresh_token: str | None
) -> OAuthCredential:
    refresh_token = payload.get("refresh_token") or fallback_refresh_token
    if not refresh_token:
        raise AuthenticationError("OAuth token response has no `refresh_token`", payload=payload)
    return OAuthCredential(
        access_token=_require(payload, "access_token"),
        refresh_token=str(refresh_token),
        expires_at=time.time() + float(_require(payload, "expires_in")),
        client_id=client_id,
        token_endpoint=token_endpoint,
    )


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
        "token_endpoint_auth_method": "none",
    }
    return _require(_payload(client.post(metadata.registration_endpoint, json=body)), "client_id")


def build_authorization_url(
    metadata: AuthServerMetadata,
    *,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    state: str,
    resource: str,
    scope: str = OAUTH_SCOPE,
) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": PKCE_METHOD,
            "state": state,
            "resource": resource,
            "scope": scope,
        }
    )
    separator = "&" if "?" in metadata.authorization_endpoint else "?"
    return f"{metadata.authorization_endpoint}{separator}{query}"


def exchange_code(
    metadata: AuthServerMetadata,
    *,
    client_id: str,
    code: str,
    code_verifier: str,
    redirect_uri: str,
    resource: str,
    client: httpx2.Client,
) -> OAuthCredential:
    form = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
        "resource": resource,
    }
    response = client.post(metadata.token_endpoint, data=form, headers=TOKEN_HEADERS)
    return _credential_from_token_payload(
        _payload(response), client_id=client_id, token_endpoint=metadata.token_endpoint, fallback_refresh_token=None
    )


def refresh_request(credential: OAuthCredential) -> httpx2.Request:
    form = {
        "grant_type": "refresh_token",
        "refresh_token": credential.refresh_token,
        "client_id": credential.client_id,
    }
    return httpx2.Request("POST", credential.token_endpoint, data=form, headers=TOKEN_HEADERS)


def parse_refresh_response(response: httpx2.Response, *, credential: OAuthCredential) -> OAuthCredential:
    return _credential_from_token_payload(
        _payload(response),
        client_id=credential.client_id,
        token_endpoint=credential.token_endpoint,
        fallback_refresh_token=credential.refresh_token,
    )


def refresh(credential: OAuthCredential, *, client: httpx2.Client) -> OAuthCredential:
    return parse_refresh_response(client.send(refresh_request(credential)), credential=credential)
