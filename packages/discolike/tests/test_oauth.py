import base64
import hashlib
import time
from urllib.parse import parse_qs
from urllib.parse import urlparse

import httpx2
import pytest

from discolike import AuthenticationError
from discolike._credentials import OAuthCredential
from discolike._oauth import CLIENT_NAME
from discolike._oauth import AuthServerMetadata
from discolike._oauth import OAuthError
from discolike._oauth import build_authorization_url
from discolike._oauth import discover
from discolike._oauth import exchange_code
from discolike._oauth import pkce_pair
from discolike._oauth import refresh
from discolike._oauth import register_client

BASE_URL = "https://api.test/v1"
METADATA = AuthServerMetadata(
    authorization_endpoint="https://auth.test/oauth/2.1/authorize",
    token_endpoint="https://auth.test/oauth/2.1/token",
    registration_endpoint="https://auth.test/oauth/2.1/register",
    issuer="https://auth.test/oauth/2.1",
)


def client_for(handler) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def form(request: httpx2.Request) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(request.content.decode()).items()}


def test_pkce_pair_is_s256() -> None:
    verifier, challenge = pkce_pair()
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == expected
    assert "=" not in verifier
    assert 43 <= len(verifier) <= 128


def test_discover_reads_well_known_under_base_url() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(
            200,
            json={
                "issuer": METADATA.issuer,
                "authorization_endpoint": METADATA.authorization_endpoint,
                "token_endpoint": METADATA.token_endpoint,
                "registration_endpoint": METADATA.registration_endpoint,
            },
        )

    assert discover(BASE_URL + "/", client=client_for(handler)) == METADATA
    assert str(seen[0].url) == "https://api.test/v1/.well-known/oauth-authorization-server"


def test_discover_missing_field_raises() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"authorization_endpoint": "x", "token_endpoint": "y"})

    with pytest.raises(AuthenticationError, match="registration_endpoint"):
        discover(BASE_URL, client=client_for(handler))


def test_register_client_sends_public_client_metadata() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(201, json={"client_id": "client-abc", "client_secret": ""})

    client_id = register_client(METADATA, redirect_uris=["http://127.0.0.1:9999/callback"], client=client_for(handler))
    assert client_id == "client-abc"
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url) == METADATA.registration_endpoint
    body = httpx2.Response(200, content=request.content).json()
    assert body["client_name"] == CLIENT_NAME
    assert body["redirect_uris"] == ["http://127.0.0.1:9999/callback"]
    assert body["grant_types"] == ["authorization_code", "refresh_token"]
    assert body["response_types"] == ["code"]
    assert body["token_endpoint_auth_method"] == "none"


def test_build_authorization_url_carries_pkce_state_and_resource() -> None:
    url = build_authorization_url(
        METADATA,
        client_id="client-abc",
        redirect_uri="http://127.0.0.1:9999/callback",
        code_challenge="chal",
        state="st",
        resource=BASE_URL,
    )
    parsed = urlparse(url)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == METADATA.authorization_endpoint
    query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
    assert query == {
        "response_type": "code",
        "client_id": "client-abc",
        "redirect_uri": "http://127.0.0.1:9999/callback",
        "code_challenge": "chal",
        "code_challenge_method": "S256",
        "state": "st",
        "resource": BASE_URL,
        "scope": "offline_access",
    }


def test_exchange_code_posts_form_and_builds_credential() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(
            200, json={"access_token": "at", "refresh_token": "rt", "expires_in": 3600, "token_type": "Bearer"}
        )

    before = time.time()
    credential = exchange_code(
        METADATA,
        client_id="client-abc",
        code="the-code",
        code_verifier="ver",
        redirect_uri="http://127.0.0.1:9999/callback",
        resource=BASE_URL,
        client=client_for(handler),
    )
    request = seen[0]
    assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert form(request) == {
        "grant_type": "authorization_code",
        "client_id": "client-abc",
        "code": "the-code",
        "code_verifier": "ver",
        "redirect_uri": "http://127.0.0.1:9999/callback",
        "resource": BASE_URL,
    }
    assert credential.access_token == "at"
    assert credential.refresh_token == "rt"
    assert credential.client_id == "client-abc"
    assert credential.token_endpoint == METADATA.token_endpoint
    assert before + 3600 <= credential.expires_at <= time.time() + 3600


def test_exchange_code_without_refresh_token_raises() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"access_token": "at", "expires_in": 3600})

    with pytest.raises(AuthenticationError, match="refresh_token"):
        exchange_code(
            METADATA,
            client_id="c",
            code="x",
            code_verifier="v",
            redirect_uri="http://127.0.0.1:1/callback",
            resource=BASE_URL,
            client=client_for(handler),
        )


def test_oauth_error_body_maps_to_authentication_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(400, json={"error": "invalid_grant", "error_description": "code expired"})

    with pytest.raises(OAuthError, match="invalid_grant: code expired") as exc_info:
        exchange_code(
            METADATA,
            client_id="c",
            code="x",
            code_verifier="v",
            redirect_uri="http://127.0.0.1:1/callback",
            resource=BASE_URL,
            client=client_for(handler),
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.error == "invalid_grant"


def test_non_json_error_maps_to_authentication_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(502, text="bad gateway")

    with pytest.raises(AuthenticationError, match="502"):
        discover(BASE_URL, client=client_for(handler))


def test_refresh_rotates_tokens_and_keeps_old_refresh_token_when_absent() -> None:
    credential = OAuthCredential(
        access_token="old",
        refresh_token="rt-old",
        expires_at=0.0,
        client_id="c",
        token_endpoint=METADATA.token_endpoint,
    )
    seen: list[httpx2.Request] = []

    def rotating(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json={"access_token": "new", "refresh_token": "rt-new", "expires_in": 60})

    rotated = refresh(credential, client=client_for(rotating))
    assert form(seen[0]) == {"grant_type": "refresh_token", "refresh_token": "rt-old", "client_id": "c"}
    assert (rotated.access_token, rotated.refresh_token) == ("new", "rt-new")
    assert rotated.client_id == "c"
    assert rotated.token_endpoint == METADATA.token_endpoint

    def not_rotating(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"access_token": "newer", "expires_in": 60})

    kept = refresh(rotated, client=client_for(not_rotating))
    assert (kept.access_token, kept.refresh_token) == ("newer", "rt-new")


def test_credential_config_roundtrip_and_expiry() -> None:
    credential = OAuthCredential(
        access_token="a", refresh_token="r", expires_at=1000.0, client_id="c", token_endpoint="https://t"
    )
    assert OAuthCredential.from_config(credential.to_config()) == credential
    assert credential.expires_within(60, now=950.0)
    assert not credential.expires_within(60, now=900.0)
