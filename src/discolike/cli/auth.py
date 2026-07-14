from __future__ import annotations

import json
import os
import sys

import typer

from discolike._config import ENV_API_KEY, KEYS_URL, delete_config, load_config, resolve_api_key, save_config
from discolike.cli._output import emit, handle_errors

app = typer.Typer(help="Manage API credentials")

MASKED_VISIBLE_CHARS = 4


def _mask(key: str) -> str:
    return "…" + key[-MASKED_VISIBLE_CHARS:]


@app.command()
@handle_errors
def login(
    api_key: str | None = typer.Option(None, help=f"API key. Create one at {KEYS_URL}"),
) -> None:
    from discolike.cli.main import build_client

    key = api_key or typer.prompt("API key", hide_input=True)
    build_client(api_key=key).account.usage()
    save_config({"auth_method": "api_key", "api_key": key})
    print(json.dumps({"logged_in": True, "source": "api_key"}), file=sys.stderr)


@app.command()
@handle_errors
def status() -> None:
    from discolike.cli.main import build_client

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
    delete_config()
    emit({"logged_out": True})
