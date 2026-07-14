from __future__ import annotations

from typing import Any

import typer

from discolike import Discolike
from discolike._version import __version__
from discolike.cli import account
from discolike.cli import auth
from discolike.cli import company
from discolike.cli import contacts
from discolike.cli import discogen
from discolike.cli import discover
from discolike.cli import enrich
from discolike.cli import match
from discolike.cli import queries

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
app.add_typer(company.app, name="company")
app.add_typer(contacts.app, name="contacts")
app.add_typer(discogen.app, name="discogen")
app.add_typer(queries.app, name="queries")
app.add_typer(account.app, name="account")
app.command(name="discover")(discover.discover_command)
app.command(name="count")(discover.count_command)
app.command(name="match")(match.match_command)
app.command(name="extract")(company.extract_command)
app.command(name="validate-icp")(enrich.validate_icp_command)
app.command(name="append")(enrich.append_command)
app.command(name="segment")(enrich.segment_command)
