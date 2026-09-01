from __future__ import annotations

from importlib.metadata import version as package_version

import typer

from discolike._config import DEFAULT_BASE_URL
from discolike.signup import signup
from discolike_cli._output import emit
from discolike_cli._output import handle_errors

FORMAT_HELP = "Output format: json or table (table auto-selected on a TTY; falls back to JSON for non-tabular data)."
CLI_AGENT = f"discolike-cli/{package_version('discolike-cli')}"


@handle_errors
def signup_command(
    ctx: typer.Context,
    email: str = typer.Option(..., "--email", help="The person's work email. Becomes the login."),
    first_name: str = typer.Option(..., "--first-name"),
    last_name: str = typer.Option(..., "--last-name"),
    agent: str | None = typer.Option(None, "--agent", help="Agent or framework name to record with the signup."),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Create a DiscoLike account for a person. No login needed; they confirm by email."""
    base_url = ctx.obj.get("base_url") or DEFAULT_BASE_URL
    emit(
        signup(email=email, first_name=first_name, last_name=last_name, agent=agent or CLI_AGENT, base_url=base_url),
        fmt=fmt,
    )
