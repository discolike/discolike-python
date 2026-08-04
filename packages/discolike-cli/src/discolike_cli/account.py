from __future__ import annotations

import typer

from discolike_cli._output import emit
from discolike_cli._output import handle_errors

FORMAT_HELP = "Output format: json or table (table auto-selected on a TTY; falls back to JSON for non-tabular data)."

app = typer.Typer(help="Account usage and quota.")


@app.command("usage")
@handle_errors
def usage_command(
    ctx: typer.Context,
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Month-to-date usage: requests, records, and spend."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).account.usage(), fmt=fmt)
