from __future__ import annotations

import typer

from discolike.cli._output import emit
from discolike.cli._output import handle_errors

app = typer.Typer(help="Account usage and billing")


@app.command("usage")
@handle_errors
def usage_command(ctx: typer.Context) -> None:
    from discolike.cli.main import get_client

    emit(get_client(ctx).account.usage())
