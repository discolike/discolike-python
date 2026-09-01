from __future__ import annotations

import json
import secrets
import sys
import webbrowser
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import NoReturn
from urllib.parse import urlparse

import httpx2
import typer

from discolike._config import AUTH_METHOD_API_KEY
from discolike._config import AUTH_METHOD_OAUTH
from discolike._config import DEFAULT_BASE_URL
from discolike._config import KEYS_URL
from discolike._config import NO_CREDENTIAL_MESSAGE
from discolike._config import delete_credential
from discolike._config import delete_oauth_client
from discolike._config import load_credential
from discolike._config import load_oauth_client
from discolike._config import save_config
from discolike._config import save_credential
from discolike._config import save_oauth_client
from discolike._credentials import OAuthClientRegistration
from discolike._credentials import OAuthCredential
from discolike._exceptions import AuthenticationError
from discolike._oauth import AuthServerMetadata
from discolike._oauth import OAuthError
from discolike._oauth import build_authorization_url
from discolike._oauth import discover
from discolike._oauth import exchange_code
from discolike._oauth import register_client
from discolike_cli._loopback import CallbackServer
from discolike_cli._output import emit
from discolike_cli._output import handle_errors
from discolike_cli.signup import run_signup

app = typer.Typer(help="Manage credentials: log in (browser or API key), check status, log out.")

MASKED_VISIBLE_CHARS = 4
LOGIN_TIMEOUT_SECONDS = 180.0
OAUTH_HTTP_TIMEOUT_SECONDS = 30.0
STATE_BYTES = 16
RANDOM_PORT = 0

SOURCE_OPTION = "option"
SOURCE_ENV = "env"
SOURCE_CONFIG = "config"

LOGIN_METHODS = (AUTH_METHOD_OAUTH, AUTH_METHOD_API_KEY)
DEAD_CLIENT_ERRORS = frozenset({"invalid_client", "unauthorized_client"})


HAS_ACCOUNT_PROMPT = "Do you already have a DiscoLike account?"
SIGNUP_FOLLOWUP_MESSAGE = "Confirm the email, then run `discolike auth login` again to sign in."


class _DeadClientError(Exception):
    """The authorization server no longer recognises the registered client_id."""


def _mask(key: str) -> str:
    return "…" + key[-MASKED_VISIBLE_CHARS:]


def _is_interactive() -> bool:
    return sys.stdin.isatty()


def _was_passed_on_command_line(ctx: typer.Context, name: str) -> bool:
    source = ctx.find_root().get_parameter_source(name)
    return source is not None and source.name == "COMMANDLINE"


def _offer_signup(ctx: typer.Context) -> None:
    email = typer.prompt("Work email")
    first_name = typer.prompt("First name")
    last_name = typer.prompt("Last name")
    base_url = str(ctx.obj.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
    run_signup(
        email=email, first_name=first_name, last_name=last_name, agent=None, base_url=base_url, yes=False, fmt=None
    )
    typer.echo(SIGNUP_FOLLOWUP_MESSAGE)
    raise typer.Exit(code=0)


def _iso(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()


def _global_key_source(ctx: typer.Context) -> str:
    # typer vendors click without re-exporting ParameterSource, so match on the enum member name.
    source = ctx.find_root().get_parameter_source("api_key")
    return SOURCE_ENV if source is not None and source.name == "ENVIRONMENT" else SOURCE_OPTION


def _verify(ctx: typer.Context, **kwargs: Any) -> None:  # noqa: ANN401 -- forwarded verbatim to build_client
    from discolike_cli.main import build_client

    base_url = ctx.obj.get("base_url")
    if base_url is not None:
        kwargs["base_url"] = base_url
    build_client(**kwargs).account.usage()


def _abort_login(message: str) -> NoReturn:
    print(json.dumps({"error": "LoginError", "message": message}), file=sys.stderr)
    raise typer.Exit(code=1)


def _registered_port(registration: OAuthClientRegistration) -> int:
    return int(urlparse(registration.redirect_uri).port or RANDOM_PORT)


def _reusable_registration(*, issuer: str, port: int) -> OAuthClientRegistration | None:
    stored = load_oauth_client()
    if stored is None or stored.issuer != issuer:
        return None
    if port != RANDOM_PORT and _registered_port(stored) != port:
        return None
    return stored


def _bind_stored_port(registration: OAuthClientRegistration) -> CallbackServer | None:
    try:
        return CallbackServer(port=_registered_port(registration))
    except OSError:
        return None


def _register_or_reuse(
    metadata: AuthServerMetadata, *, port: int, http: httpx2.Client
) -> tuple[CallbackServer, OAuthClientRegistration, bool]:
    # PropelAuth matches the redirect URI literally (port included) and remembers consent per client_id,
    # so a stored registration is only worth reusing when its exact port can be bound again.
    stored = _reusable_registration(issuer=metadata.issuer, port=port)
    if stored is not None:
        server = _bind_stored_port(stored)
        if server is not None:
            return server, stored, True
    server = CallbackServer(port=port)
    client_id = register_client(metadata, redirect_uris=[server.redirect_uri], client=http)
    registration = OAuthClientRegistration(
        client_id=client_id, redirect_uri=server.redirect_uri, issuer=metadata.issuer
    )
    save_oauth_client(registration)
    return server, registration, False


def _authorize(
    metadata: AuthServerMetadata,
    registration: OAuthClientRegistration,
    server: CallbackServer,
    *,
    resource: str,
    open_browser: bool,
    http: httpx2.Client,
) -> OAuthCredential:
    state = secrets.token_urlsafe(STATE_BYTES)
    url, verifier = build_authorization_url(
        metadata,
        client_id=registration.client_id,
        redirect_uri=registration.redirect_uri,
        state=state,
        resource=resource,
    )
    print(f"Open this URL in your browser to log in:\n{url}", file=sys.stderr)
    if open_browser and not webbrowser.open(url):
        print("Could not open a browser; open the URL above manually.", file=sys.stderr)
    callback = server.wait(timeout=LOGIN_TIMEOUT_SECONDS)
    if callback is None:
        _abort_login(f"Timed out after {LOGIN_TIMEOUT_SECONDS:.0f}s waiting for the browser login")
    if callback.get("state") != state:
        _abort_login("Invalid OAuth callback (state mismatch)")
    if "error" in callback:
        message = f"Authorization failed: {callback.get('error_description') or callback['error']}"
        if callback["error"] in DEAD_CLIENT_ERRORS:
            raise _DeadClientError(message)
        _abort_login(message)
    if "code" not in callback:
        _abort_login("Invalid OAuth callback (missing code)")
    try:
        return exchange_code(
            metadata,
            client_id=registration.client_id,
            code=callback["code"],
            code_verifier=verifier,
            redirect_uri=registration.redirect_uri,
            resource=resource,
        )
    except OAuthError as exc:
        if exc.error in DEAD_CLIENT_ERRORS:
            raise _DeadClientError(f"Token exchange failed: {exc}") from exc
        raise


def _oauth_login(ctx: typer.Context, *, open_browser: bool, port: int) -> OAuthCredential:
    base_url = str(ctx.obj.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
    with httpx2.Client(timeout=OAUTH_HTTP_TIMEOUT_SECONDS) as http:
        metadata = discover(base_url, client=http)
        server, registration, reused = _register_or_reuse(metadata, port=port, http=http)
        try:
            with server:
                return _authorize(
                    metadata, registration, server, resource=base_url, open_browser=open_browser, http=http
                )
        except _DeadClientError as exc:
            if not reused:
                _abort_login(str(exc))
        delete_oauth_client()
        server, registration, _ = _register_or_reuse(metadata, port=port, http=http)
        try:
            with server:
                return _authorize(
                    metadata, registration, server, resource=base_url, open_browser=open_browser, http=http
                )
        except _DeadClientError as exc:
            _abort_login(str(exc))


def _api_key_login(ctx: typer.Context, *, api_key: str | None) -> None:
    # An ambient DISCOLIKE_API_KEY must not silently become the saved key; only an explicit flag may.
    passed_globally = ctx.obj.get("api_key") if _global_key_source(ctx) == SOURCE_OPTION else None
    key = api_key or passed_globally or typer.prompt("API key", hide_input=True)
    _verify(ctx, api_key=key)
    save_config({"auth_method": AUTH_METHOD_API_KEY, "api_key": key})
    print(json.dumps({"logged_in": True, "source": AUTH_METHOD_API_KEY}), file=sys.stderr)


@app.command()
@handle_errors
def login(
    ctx: typer.Context,
    api_key: str | None = typer.Option(
        None, help=f"Log in with an API key instead of the browser. Create one at {KEYS_URL}."
    ),
    method: str = typer.Option(
        AUTH_METHOD_OAUTH,
        "--method",
        help="oauth (browser login, default) or api_key (prompts for a key unless --api-key is given).",
    ),
    no_browser: bool = typer.Option(False, "--no-browser", help="Print the login URL instead of opening a browser."),
    port: int = typer.Option(
        RANDOM_PORT, "--port", help="Fixed loopback port for the browser redirect (default: random; use with SSH)."
    ),
) -> None:
    """Log in via the browser (OAuth) or with an API key, verify, and save to the local config file."""
    if (
        _is_interactive()
        and api_key is None
        and not _was_passed_on_command_line(ctx, "method")
        and not typer.confirm(HAS_ACCOUNT_PROMPT, default=True)
    ):
        _offer_signup(ctx)
    if method not in LOGIN_METHODS:
        raise typer.BadParameter(f"must be one of {', '.join(LOGIN_METHODS)}", param_hint="--method")
    global_key_passed = ctx.obj.get("api_key") is not None and _global_key_source(ctx) == SOURCE_OPTION
    if api_key or global_key_passed or method == AUTH_METHOD_API_KEY:
        _api_key_login(ctx, api_key=api_key)
        return
    credential = _oauth_login(ctx, open_browser=not no_browser, port=port)
    _verify(ctx, auth=credential)
    save_credential(credential)
    print(
        json.dumps({"logged_in": True, "method": AUTH_METHOD_OAUTH, "expires_at": _iso(credential.expires_at)}),
        file=sys.stderr,
    )


@app.command()
@handle_errors
def status(ctx: typer.Context) -> None:
    """Show which credential is in use (option, env, or config) and verify it against the API."""
    key = ctx.obj.get("api_key")
    if key:
        _verify(ctx, api_key=str(key))
        emit(
            {
                "source": _global_key_source(ctx),
                "method": AUTH_METHOD_API_KEY,
                "api_key": _mask(str(key)),
                "valid": True,
            }
        )
        return
    credential = load_credential()
    if credential is None:
        raise AuthenticationError(NO_CREDENTIAL_MESSAGE)
    if isinstance(credential, OAuthCredential):
        _verify(ctx)
        emit(
            {
                "source": SOURCE_CONFIG,
                "method": AUTH_METHOD_OAUTH,
                "expires_at": _iso(credential.expires_at),
                "expired": credential.expires_within(0),
                "valid": True,
            }
        )
        return
    _verify(ctx, api_key=credential.api_key)
    emit({"source": SOURCE_CONFIG, "method": AUTH_METHOD_API_KEY, "api_key": _mask(credential.api_key), "valid": True})


@app.command()
@handle_errors
def logout() -> None:
    """Delete saved credentials from the local config file (the registered OAuth client is kept)."""
    delete_credential()
    emit({"logged_out": True})
