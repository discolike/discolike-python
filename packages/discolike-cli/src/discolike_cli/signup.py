from __future__ import annotations

import sys
from importlib.metadata import version as package_version

import typer

from discolike._config import DEFAULT_BASE_URL
from discolike._config import load_signup_email
from discolike.signup import signup
from discolike_cli._output import emit
from discolike_cli._output import handle_errors

FORMAT_HELP = "Output format: json or table (table auto-selected on a TTY; falls back to JSON for non-tabular data)."
YES_HELP = "Skip the confirmation when signing up a different email than last time."
CLI_AGENT = f"discolike-cli/{package_version('discolike-cli')}"


def _is_interactive() -> bool:
    return sys.stdin.isatty()


def _confirm_email_change(previous: str, email: str, *, yes: bool) -> bool:
    if yes:
        return True
    prompt = f"This machine already signed up {previous}. Sign up {email} as well?"
    if _is_interactive():
        return typer.confirm(prompt, default=False)
    typer.echo(f"{prompt} re-run with --yes", err=True)
    return False


def run_signup(
    *,
    email: str,
    first_name: str,
    last_name: str,
    agent: str | None,
    base_url: str,
    yes: bool,
    fmt: str | None,
) -> None:
    previous = load_signup_email()
    allow_new_email = False
    if previous is not None and previous.lower() != email.lower():
        if not _confirm_email_change(previous, email, yes=yes):
            raise typer.Exit(code=1)
        allow_new_email = True
    emit(
        signup(
            email=email,
            first_name=first_name,
            last_name=last_name,
            agent=agent or CLI_AGENT,
            base_url=base_url,
            allow_new_email=allow_new_email,
        ),
        fmt=fmt,
    )


@handle_errors
def signup_command(
    ctx: typer.Context,
    email: str = typer.Option(..., "--email", help="The person's work email. Becomes the login."),
    first_name: str = typer.Option(..., "--first-name"),
    last_name: str = typer.Option(..., "--last-name"),
    agent: str | None = typer.Option(None, "--agent", help="Agent or framework name to record with the signup."),
    yes: bool = typer.Option(False, "--yes", "-y", help=YES_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Create a DiscoLike account for a person. No login needed; they confirm by email."""
    base_url = ctx.obj.get("base_url") or DEFAULT_BASE_URL
    run_signup(
        email=email, first_name=first_name, last_name=last_name, agent=agent, base_url=base_url, yes=yes, fmt=fmt
    )
