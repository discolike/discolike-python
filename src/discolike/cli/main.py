from __future__ import annotations

from typing import Any

import typer

from discolike import Discolike
from discolike._version import __version__
from discolike.cli import auth

app = typer.Typer(
    name="discolike",
    no_args_is_help=True,
    help="DiscoLike API from your terminal — https://docs.discolike.com",
)

build_client = Discolike


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    api_key: str | None = typer.Option(None, envvar="DISCOLIKE_API_KEY"),
    base_url: str | None = typer.Option(None),
    version: bool = typer.Option(False, "--version"),
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit
    ctx.obj = {"api_key": api_key, "base_url": base_url}


def get_client(ctx: typer.Context) -> Discolike:
    kwargs: dict[str, Any] = {k: v for k, v in ctx.obj.items() if v is not None}
    return build_client(**kwargs)


app.add_typer(auth.app, name="auth")
