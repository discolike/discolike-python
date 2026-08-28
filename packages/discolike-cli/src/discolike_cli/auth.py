from __future__ import annotations

import json
import secrets
import sys
import webbrowser
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import NoReturn

import httpx2
import typer

from discolike._config import AUTH_METHOD_API_KEY
from discolike._config import AUTH_METHOD_OAUTH
from discolike._config import DEFAULT_BASE_URL
from discolike._config import KEYS_URL
from discolike._config import NO_CREDENTIAL_MESSAGE
from discolike._config import delete_config
from discolike._config import load_credential
from discolike._config import save_config
from discolike._config import save_credential
from discolike._credentials import OAuthCredential
from discolike._exceptions import AuthenticationError
from discolike._oauth import build_authorization_url
from discolike._oauth import discover
from discolike._oauth import exchange_code
from discolike._oauth import pkce_pair
from discolike._oauth import register_client
from discolike_cli._loopback import CallbackServer
from discolike_cli._output import emit
from discolike_cli._output import handle_errors

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


def _mask(key: str) -> str:
    return "…" + key[-MASKED_VISIBLE_CHARS:]


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


def _oauth_login(ctx: typer.Context, *, open_browser: bool, port: int) -> OAuthCredential:
    base_url = str(ctx.obj.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
    with httpx2.Client(timeout=OAUTH_HTTP_TIMEOUT_SECONDS) as http, CallbackServer(port=port) as server:
        metadata = discover(base_url, client=http)
        redirect_uri = server.redirect_uri
        client_id = register_client(metadata, redirect_uris=[redirect_uri], client=http)
        verifier, challenge = pkce_pair()
        state = secrets.token_urlsafe(STATE_BYTES)
        url = build_authorization_url(
            metadata,
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=challenge,
            state=state,
            resource=base_url,
        )
        print(f"Open this URL in your browser to log in:\n{url}", file=sys.stderr)
        if open_browser and not webbrowser.open(url):
            print("Could not open a browser; open the URL above manually.", file=sys.stderr)
        callback = server.wait(timeout=LOGIN_TIMEOUT_SECONDS)
        if callback is None:
            _abort_login(f"Timed out after {LOGIN_TIMEOUT_SECONDS:.0f}s waiting for the browser login")
        if "error" in callback:
            _abort_login(f"Authorization failed: {callback.get('error_description') or callback['error']}")
        if callback.get("state") != state or "code" not in callback:
            _abort_login("Invalid OAuth callback (state mismatch or missing code)")
        return exchange_code(
            metadata,
            client_id=client_id,
            code=callback["code"],
            code_verifier=verifier,
            redirect_uri=redirect_uri,
            resource=base_url,
            client=http,
        )


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
    """Delete saved credentials from the local config file."""
    delete_config()
    emit({"logged_out": True})
