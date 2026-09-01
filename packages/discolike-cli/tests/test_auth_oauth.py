from __future__ import annotations

import dataclasses
import json
import socket
import threading
import time
from collections.abc import Callable
from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qs
from urllib.parse import urlparse
from urllib.request import urlopen

import httpx2
import pytest
from typer.testing import CliRunner

import discolike_cli.auth as auth_module
from discolike._config import DEFAULT_BASE_URL
from discolike._config import config_path
from discolike._config import load_credential
from discolike._config import load_oauth_client
from discolike._config import save_credential
from discolike._config import save_oauth_client
from discolike._credentials import ApiKeyCredential
from discolike._credentials import OAuthClientRegistration
from discolike._credentials import OAuthCredential
from discolike._oauth import AuthServerMetadata
from discolike._oauth import OAuthError
from discolike_cli.main import app
from discolike_testkit import Handler

runner = CliRunner()

METADATA = AuthServerMetadata(
    authorization_endpoint="https://auth.test/oauth/2.1/authorize",
    token_endpoint="https://auth.test/oauth/2.1/token",
    registration_endpoint="https://auth.test/oauth/2.1/register",
    issuer="https://auth.test/oauth/2.1",
)
CREDENTIAL = OAuthCredential(
    access_token="at-1",
    refresh_token="rt-1",
    expires_at=1_800_000_000.0,
    client_id="client-1",
    token_endpoint=METADATA.token_endpoint,
)


def _usage_ok(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(200, json={"requests_mtd": 1})


def _usage_unauthorized(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(401, json={"detail": "Invalid API Key or Session"})


class FakeProvider:
    """Stands in for the authorization server and the user's browser."""

    def __init__(self) -> None:
        self.real_build_authorization_url = auth_module.build_authorization_url
        self.discover_calls: list[str] = []
        self.register_calls: list[list[str]] = []
        self.exchange_calls: list[dict[str, Any]] = []
        self.opened_urls: list[str] = []
        self.exchange_failures: list[OAuthError] = []
        self.callback_query: Callable[[dict[str, str]], str] = lambda query: f"code=the-code&state={query['state']}"

    def discover(self, base_url: str, *, client: httpx2.Client) -> AuthServerMetadata:
        self.discover_calls.append(base_url)
        return METADATA

    def register_client(self, metadata: AuthServerMetadata, *, redirect_uris: list[str], client: httpx2.Client) -> str:
        self.register_calls.append(redirect_uris)
        return "client-1"

    def exchange_code(self, metadata: AuthServerMetadata, **kwargs: Any) -> OAuthCredential:
        self.exchange_calls.append(kwargs)
        if self.exchange_failures:
            raise self.exchange_failures.pop(0)
        return CREDENTIAL

    def build_authorization_url(self, metadata: AuthServerMetadata, **kwargs: Any) -> tuple[str, str]:
        url, verifier = self.real_build_authorization_url(metadata, **kwargs)
        query = {key: values[0] for key, values in parse_qs(urlparse(url).query).items()}
        callback = f"{query['redirect_uri']}?{self.callback_query(query)}"
        threading.Thread(target=lambda: urlopen(callback).read(), daemon=True).start()  # noqa: S310 -- loopback test server
        return url, verifier

    def open(self, url: str) -> bool:
        self.opened_urls.append(url)
        return True


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    fake = FakeProvider()
    monkeypatch.setattr(auth_module, "discover", fake.discover)
    monkeypatch.setattr(auth_module, "register_client", fake.register_client)
    monkeypatch.setattr(auth_module, "exchange_code", fake.exchange_code)
    monkeypatch.setattr(auth_module, "build_authorization_url", fake.build_authorization_url)
    monkeypatch.setattr(auth_module.webbrowser, "open", fake.open)
    return fake


def test_login_default_runs_oauth_loopback_flow(
    provider: FakeProvider,
    install_build_client: Callable[[Handler], None],
    build_client_calls: list[dict[str, Any]],
) -> None:
    install_build_client(_usage_ok)
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 0, result.output
    assert provider.discover_calls == [DEFAULT_BASE_URL]
    redirect_uri = provider.register_calls[0][0]
    assert redirect_uri.startswith("http://127.0.0.1:")
    assert redirect_uri.endswith("/callback")
    exchange = provider.exchange_calls[0]
    assert exchange["code"] == "the-code"
    assert exchange["client_id"] == "client-1"
    assert exchange["redirect_uri"] == redirect_uri
    assert exchange["resource"] == DEFAULT_BASE_URL
    assert len(provider.opened_urls) == 1
    assert build_client_calls == [{"auth": CREDENTIAL}]
    stored = json.loads(config_path().read_text())
    assert (stored["auth_method"], stored["oauth"]) == ("oauth", CREDENTIAL.to_config())
    assert stored["oauth_client"] == {"client_id": "client-1", "redirect_uri": redirect_uri, "issuer": METADATA.issuer}
    payload = json.loads(result.stderr.splitlines()[-1])
    assert payload == {"logged_in": True, "method": "oauth", "expires_at": "2027-01-15T08:00:00+00:00"}
    assert provider.opened_urls[0] in result.stderr


def test_login_no_browser_and_fixed_port(
    provider: FakeProvider, install_build_client: Callable[[Handler], None]
) -> None:
    install_build_client(_usage_ok)
    result = runner.invoke(
        app, ["--base-url", "https://api.dev.test/v1/", "auth", "login", "--no-browser", "--port", "18484"]
    )
    assert result.exit_code == 0, result.output
    assert provider.opened_urls == []
    assert provider.register_calls == [["http://127.0.0.1:18484/callback"]]
    assert provider.discover_calls == ["https://api.dev.test/v1"]
    assert provider.exchange_calls[0]["resource"] == "https://api.dev.test/v1"


def test_login_state_mismatch_exits_1_and_saves_nothing(
    provider: FakeProvider, install_build_client: Callable[[Handler], None]
) -> None:
    install_build_client(_usage_ok)
    provider.callback_query = lambda query: "code=the-code&state=forged"
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 1
    assert load_credential() is None
    assert provider.exchange_calls == []
    assert json.loads(result.stderr.splitlines()[-1])["error"] == "LoginError"


def test_login_user_denied_exits_1(provider: FakeProvider, install_build_client: Callable[[Handler], None]) -> None:
    install_build_client(_usage_ok)
    provider.callback_query = lambda query: f"error=access_denied&error_description=nope&state={query['state']}"
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 1
    assert "nope" in json.loads(result.stderr.splitlines()[-1])["message"]


def test_login_timeout_exits_1(
    provider: FakeProvider, install_build_client: Callable[[Handler], None], monkeypatch: pytest.MonkeyPatch
) -> None:
    install_build_client(_usage_ok)
    monkeypatch.setattr(auth_module, "LOGIN_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(
        auth_module, "build_authorization_url", lambda metadata, **kwargs: ("https://auth.test/never", "v")
    )
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 1
    assert "Timed out" in json.loads(result.stderr.splitlines()[-1])["message"]
    assert load_credential() is None


def test_login_oauth_verify_failure_exits_3_and_saves_nothing(
    provider: FakeProvider, install_build_client: Callable[[Handler], None]
) -> None:
    install_build_client(_usage_unauthorized)
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 3
    assert load_credential() is None
    assert json.loads(result.stderr.splitlines()[-1])["error"] == "AuthenticationError"


def test_login_rejects_unknown_method(provider: FakeProvider) -> None:
    result = runner.invoke(app, ["auth", "login", "--method", "magic"])
    assert result.exit_code == 2
    assert provider.discover_calls == []


def test_status_reports_oauth_credential(
    install_build_client: Callable[[Handler], None], build_client_calls: list[dict[str, Any]]
) -> None:
    install_build_client(_usage_ok)
    save_credential(CREDENTIAL)
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0, result.output
    assert build_client_calls == [{}]
    assert json.loads(result.stdout) == {
        "source": "config",
        "method": "oauth",
        "expires_at": "2027-01-15T08:00:00+00:00",
        "expired": False,
        "valid": True,
    }


def test_status_flags_expired_oauth_credential(install_build_client: Callable[[Handler], None]) -> None:
    install_build_client(_usage_ok)
    save_credential(dataclasses.replace(CREDENTIAL, expires_at=time.time() - 1))
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["expired"] is True


def test_status_reports_api_key_method(install_build_client: Callable[[Handler], None]) -> None:
    install_build_client(_usage_ok)
    result = runner.invoke(app, ["--api-key", "dk-abcdefgh1234", "auth", "status"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["method"] == "api_key"


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _registration(port: int, *, issuer: str = METADATA.issuer) -> OAuthClientRegistration:
    return OAuthClientRegistration(
        client_id="stored-client", redirect_uri=f"http://127.0.0.1:{port}/callback", issuer=issuer
    )


def test_login_reuses_stored_client_when_its_port_is_free(
    provider: FakeProvider, install_build_client: Callable[[Handler], None]
) -> None:
    install_build_client(_usage_ok)
    port = _free_port()
    save_oauth_client(_registration(port))
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 0, result.output
    assert provider.register_calls == []
    assert provider.exchange_calls[0]["client_id"] == "stored-client"
    assert provider.exchange_calls[0]["redirect_uri"] == f"http://127.0.0.1:{port}/callback"
    assert load_oauth_client() == _registration(port)
    assert json.loads(config_path().read_text())["auth_method"] == "oauth"


def test_login_registers_anew_when_stored_port_is_busy(
    provider: FakeProvider, install_build_client: Callable[[Handler], None]
) -> None:
    install_build_client(_usage_ok)
    with socket.socket() as blocker:
        blocker.bind(("127.0.0.1", 0))
        blocker.listen()
        busy_port = blocker.getsockname()[1]
        save_oauth_client(_registration(busy_port))
        result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 0, result.output
    new_uri = provider.register_calls[0][0]
    assert new_uri != f"http://127.0.0.1:{busy_port}/callback"
    stored = load_oauth_client()
    assert stored is not None
    assert (stored.client_id, stored.redirect_uri) == ("client-1", new_uri)


def test_login_registers_anew_for_a_different_issuer(
    provider: FakeProvider, install_build_client: Callable[[Handler], None]
) -> None:
    install_build_client(_usage_ok)
    save_oauth_client(_registration(_free_port(), issuer="https://auth.other/oauth/2.1"))
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 0, result.output
    assert len(provider.register_calls) == 1
    stored = load_oauth_client()
    assert stored is not None
    assert stored.issuer == METADATA.issuer


def test_login_explicit_port_differing_from_stored_registers_anew(
    provider: FakeProvider, install_build_client: Callable[[Handler], None]
) -> None:
    install_build_client(_usage_ok)
    save_oauth_client(_registration(_free_port()))
    wanted = _free_port()
    result = runner.invoke(app, ["auth", "login", "--port", str(wanted)])
    assert result.exit_code == 0, result.output
    assert provider.register_calls == [[f"http://127.0.0.1:{wanted}/callback"]]


def test_logout_keeps_stored_client_and_drops_credential(install_build_client: Callable[[Handler], None]) -> None:
    install_build_client(_usage_ok)
    save_oauth_client(_registration(18484))
    save_credential(CREDENTIAL)
    result = runner.invoke(app, ["auth", "logout"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"logged_out": True}
    assert load_credential() is None
    assert load_oauth_client() == _registration(18484)
    status = runner.invoke(app, ["auth", "status"])
    assert status.exit_code == 3
    assert "discolike auth login" in json.loads(status.stderr)["message"]


def test_logout_with_api_key_config_removes_the_key_but_keeps_stored_client() -> None:
    save_oauth_client(_registration(18484))
    save_credential(ApiKeyCredential(api_key="dk-1"))
    result = runner.invoke(app, ["auth", "logout"])
    assert result.exit_code == 0, result.output
    stored = json.loads(config_path().read_text())
    assert "api_key" not in stored
    assert "auth_method" not in stored
    assert load_oauth_client() == _registration(18484)


def _dead_then_ok(query: dict[str, str]) -> str:
    if query["client_id"] == "stored-client":
        return f"error=invalid_client&error_description=unknown+client&state={query['state']}"
    return f"code=the-code&state={query['state']}"


def test_login_reregisters_when_authorize_rejects_the_stored_client(
    provider: FakeProvider, install_build_client: Callable[[Handler], None]
) -> None:
    install_build_client(_usage_ok)
    save_oauth_client(_registration(_free_port()))
    provider.callback_query = _dead_then_ok
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 0, result.output
    assert len(provider.register_calls) == 1
    assert [call["client_id"] for call in provider.exchange_calls] == ["client-1"]
    stored = load_oauth_client()
    assert stored is not None
    assert (stored.client_id, stored.redirect_uri) == ("client-1", provider.register_calls[0][0])
    assert load_credential() == CREDENTIAL


def test_login_reregisters_when_exchange_rejects_the_stored_client(
    provider: FakeProvider, install_build_client: Callable[[Handler], None]
) -> None:
    install_build_client(_usage_ok)
    save_oauth_client(_registration(_free_port()))
    provider.exchange_failures = [OAuthError("invalid_client: gone", error="invalid_client", status_code=400)]
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 0, result.output
    assert [call["client_id"] for call in provider.exchange_calls] == ["stored-client", "client-1"]
    assert len(provider.register_calls) == 1
    stored = load_oauth_client()
    assert stored is not None
    assert stored.client_id == "client-1"
    assert load_credential() == CREDENTIAL


def test_login_fresh_client_rejected_is_a_login_error_without_retry(
    provider: FakeProvider, install_build_client: Callable[[Handler], None]
) -> None:
    install_build_client(_usage_ok)
    provider.callback_query = lambda query: f"error=unauthorized_client&state={query['state']}"
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 1
    assert len(provider.register_calls) == 1
    assert provider.exchange_calls == []
    assert json.loads(result.stderr.splitlines()[-1]) == {
        "error": "LoginError",
        "message": "Authorization failed: unauthorized_client",
    }


def test_login_reused_client_rejected_twice_is_a_login_error(
    provider: FakeProvider, install_build_client: Callable[[Handler], None]
) -> None:
    install_build_client(_usage_ok)
    save_oauth_client(_registration(_free_port()))
    provider.callback_query = lambda query: f"error=invalid_client&state={query['state']}"
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 1
    assert len(provider.register_calls) == 1
    assert json.loads(result.stderr.splitlines()[-1])["error"] == "LoginError"


def test_login_access_denied_keeps_stored_client(
    provider: FakeProvider, install_build_client: Callable[[Handler], None]
) -> None:
    install_build_client(_usage_ok)
    registration = _registration(_free_port())
    save_oauth_client(registration)
    provider.callback_query = lambda query: f"error=access_denied&state={query['state']}"
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 1
    assert provider.register_calls == []
    assert load_oauth_client() == registration


def test_login_forged_error_callback_cannot_evict_stored_client(
    provider: FakeProvider, install_build_client: Callable[[Handler], None]
) -> None:
    install_build_client(_usage_ok)
    registration = _registration(_free_port())
    save_oauth_client(registration)
    provider.callback_query = lambda query: "error=invalid_client&state=forged"
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 1
    assert "state mismatch" in json.loads(result.stderr.splitlines()[-1])["message"]
    assert provider.register_calls == []
    assert load_oauth_client() == registration


def test_login_tty_confirms_existing_account_runs_oauth(
    provider: FakeProvider,
    install_build_client: Callable[[Handler], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_build_client(_usage_ok)
    monkeypatch.setattr(auth_module, "_is_interactive", lambda: True)
    with patch("discolike_cli.auth.run_signup", autospec=True) as run_signup_mock:
        result = runner.invoke(app, ["auth", "login"], input="y\n")
    assert result.exit_code == 0, result.output
    assert provider.discover_calls == [DEFAULT_BASE_URL]
    run_signup_mock.assert_not_called()


def test_login_tty_declines_account_runs_signup(
    provider: FakeProvider,
    install_build_client: Callable[[Handler], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_build_client(_usage_ok)
    monkeypatch.setattr(auth_module, "_is_interactive", lambda: True)
    with patch("discolike_cli.auth.run_signup", autospec=True, return_value=None) as run_signup_mock:
        result = runner.invoke(app, ["auth", "login"], input="n\njane@acme.com\nJane\nDoe\n")
    assert result.exit_code == 0, result.output
    run_signup_mock.assert_called_once_with(
        email="jane@acme.com",
        first_name="Jane",
        last_name="Doe",
        agent=None,
        base_url=DEFAULT_BASE_URL,
        yes=False,
        fmt=None,
    )
    assert "run `discolike auth login` again" in result.output
    assert provider.discover_calls == []


def test_login_with_api_key_skips_account_question(install_build_client: Callable[[Handler], None]) -> None:
    install_build_client(_usage_ok)
    with patch("discolike_cli.auth.typer.confirm", autospec=True) as confirm_mock:
        result = runner.invoke(app, ["auth", "login", "--api-key", "dk-1"])
    assert result.exit_code == 0, result.output
    confirm_mock.assert_not_called()


def test_login_with_global_api_key_skips_account_question(
    install_build_client: Callable[[Handler], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_build_client(_usage_ok)
    monkeypatch.setattr(auth_module, "_is_interactive", lambda: True)
    with patch("discolike_cli.auth.typer.confirm", autospec=True) as confirm_mock:
        result = runner.invoke(app, ["--api-key", "dk-global", "auth", "login"])
    assert result.exit_code == 0, result.output
    confirm_mock.assert_not_called()
    assert json.loads(config_path().read_text())["api_key"] == "dk-global"


def test_login_with_explicit_api_key_method_skips_account_question(
    install_build_client: Callable[[Handler], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_build_client(_usage_ok)
    monkeypatch.setattr(auth_module, "_is_interactive", lambda: True)
    with patch("discolike_cli.auth.typer.confirm", autospec=True) as confirm_mock:
        result = runner.invoke(app, ["auth", "login", "--method", "api_key", "--api-key", "dk-x"])
    assert result.exit_code == 0, result.output
    confirm_mock.assert_not_called()
    assert json.loads(config_path().read_text())["api_key"] == "dk-x"


def test_login_rejects_unknown_method_on_a_tty_without_asking(
    provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_module, "_is_interactive", lambda: True)
    with patch("discolike_cli.auth.typer.confirm", autospec=True) as confirm_mock:
        result = runner.invoke(app, ["auth", "login", "--method", "bogus"])
    assert result.exit_code == 2
    confirm_mock.assert_not_called()
    assert provider.discover_calls == []
