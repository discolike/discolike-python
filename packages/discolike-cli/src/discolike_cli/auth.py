from __future__ import annotations

import json
import sys
from typing import Any

import typer

from discolike._config import KEYS_URL
from discolike._config import delete_config
from discolike._config import load_config
from discolike._config import resolve_api_key
from discolike._config import save_config
from discolike_cli._output import emit
from discolike_cli._output import handle_errors

app = typer.Typer(help="Manage API credentials: log in, check key status, log out.")

MASKED_VISIBLE_CHARS = 4

SOURCE_OPTION = "option"
SOURCE_ENV = "env"
SOURCE_CONFIG = "config"


def _mask(key: str) -> str:
    return "…" + key[-MASKED_VISIBLE_CHARS:]


def _global_key_source(ctx: typer.Context) -> str:
    # typer vendors click without re-exporting ParameterSource, so match on the enum member name.
    source = ctx.find_root().get_parameter_source("api_key")
    return SOURCE_ENV if source is not None and source.name == "ENVIRONMENT" else SOURCE_OPTION


def _verify(ctx: typer.Context, *, api_key: str) -> None:
    from discolike_cli.main import build_client

    kwargs: dict[str, Any] = {"api_key": api_key}
    base_url = ctx.obj.get("base_url")
    if base_url is not None:
        kwargs["base_url"] = base_url
    build_client(**kwargs).account.usage()


@app.command()
@handle_errors
def login(
    ctx: typer.Context,
    api_key: str | None = typer.Option(None, help=f"API key. Create one at {KEYS_URL}. Prompted for if omitted."),
) -> None:
    """Verify an API key and save it to the local config file."""
    # An ambient DISCOLIKE_API_KEY must not silently become the saved key; only an explicit flag may.
    passed_globally = ctx.obj.get("api_key") if _global_key_source(ctx) == SOURCE_OPTION else None
    key = api_key or passed_globally or typer.prompt("API key", hide_input=True)
    _verify(ctx, api_key=key)
    save_config({"auth_method": "api_key", "api_key": key})
    print(json.dumps({"logged_in": True, "source": "api_key"}), file=sys.stderr)


@app.command()
@handle_errors
def status(ctx: typer.Context) -> None:
    """Show which API key is in use (option, env, or config) and verify it against the API."""
    key = ctx.obj.get("api_key")
    source = _global_key_source(ctx)
    if not key:
        key = load_config().get("api_key")
        source = SOURCE_CONFIG
    if not key:
        resolve_api_key(None)
    _verify(ctx, api_key=str(key))
    emit({"source": source, "api_key": _mask(str(key)), "valid": True})


@app.command()
@handle_errors
def logout() -> None:
    """Delete saved credentials from the local config file."""
    delete_config()
    emit({"logged_out": True})
