from __future__ import annotations

import json
import os
import sys

import typer

from discolike._config import ENV_API_KEY
from discolike._config import KEYS_URL
from discolike._config import delete_config
from discolike._config import load_config
from discolike._config import resolve_api_key
from discolike._config import save_config
from discolike_cli._output import emit
from discolike_cli._output import handle_errors

app = typer.Typer(help="Manage API credentials: log in, check key status, log out.")

MASKED_VISIBLE_CHARS = 4


def _mask(key: str) -> str:
    return "…" + key[-MASKED_VISIBLE_CHARS:]


@app.command()
@handle_errors
def login(
    api_key: str | None = typer.Option(None, help=f"API key. Create one at {KEYS_URL}. Prompted for if omitted."),
) -> None:
    """Verify an API key and save it to the local config file."""
    from discolike_cli.main import build_client

    key = api_key or typer.prompt("API key", hide_input=True)
    build_client(api_key=key).account.usage()
    save_config({"auth_method": "api_key", "api_key": key})
    print(json.dumps({"logged_in": True, "source": "api_key"}), file=sys.stderr)


@app.command()
@handle_errors
def status() -> None:
    """Show which API key is in use (env or config) and verify it against the API."""
    from discolike_cli.main import build_client

    key = os.environ.get(ENV_API_KEY)
    source = "env"
    if not key:
        key = load_config().get("api_key")
        source = "config"
    if not key:
        resolve_api_key(None)
    build_client(api_key=key).account.usage()
    emit({"source": source, "api_key": _mask(str(key)), "valid": True})


@app.command()
@handle_errors
def logout() -> None:
    """Delete saved credentials from the local config file."""
    delete_config()
    emit({"logged_out": True})
