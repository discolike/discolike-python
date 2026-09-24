from __future__ import annotations

import sys
from importlib.metadata import version as package_version
from typing import Any

import typer
from typer import Abort
from typer._click.exceptions import ClickException
from typer._click.exceptions import NoArgsIsHelpError
from typer._click.exceptions import UsageError

from discolike import Discolike
from discolike import ValidationError
from discolike import __version__ as sdk_version
from discolike_cli import account
from discolike_cli import auth
from discolike_cli import bulk
from discolike_cli import company
from discolike_cli import contacts
from discolike_cli import discogen
from discolike_cli import discover
from discolike_cli import email
from discolike_cli import enrich
from discolike_cli import match
from discolike_cli import providers
from discolike_cli import queries
from discolike_cli import signup
from discolike_cli._help import MAIN_EPILOG
from discolike_cli._help import ContractCommand
from discolike_cli._help import ContractGroup
from discolike_cli._help import epilog
from discolike_cli._output import fail

app = typer.Typer(
    name="discolike",
    no_args_is_help=True,
    rich_markup_mode="rich",
    help=(
        "🪩 [bold]DiscoLike[/bold] — the search engine for the business web.\n\n"
        "Discover lookalike companies, size segments, enrich domain lists, match messy "
        "company names to domains, and find the right contacts — from your terminal.\n\n"
        "Docs: https://docs.discolike.com · Keys: https://app.discolike.com/account/management/keys"
    ),
    epilog=MAIN_EPILOG,
    cls=ContractGroup,
)


def _stdout_is_tty() -> bool:
    return sys.stdout.isatty()


build_client = Discolike


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    api_key: str | None = typer.Option(
        None, envvar="DISCOLIKE_API_KEY", help="API key. Overrides the config file saved by `discolike auth login`."
    ),
    base_url: str | None = typer.Option(None, help="API base URL (default: https://api.discolike.com/v1)."),
    version: bool = typer.Option(False, "--version", help="Print CLI and SDK versions and exit."),
) -> None:
    if version:
        cli_version = package_version("discolike-cli")
        if _stdout_is_tty():
            typer.echo(f"🪩 discolike-cli {cli_version} (discolike {sdk_version})")
        else:
            typer.echo(cli_version)
        raise typer.Exit
    ctx.obj = {"api_key": api_key, "base_url": base_url}


def get_client(ctx: typer.Context) -> Discolike:
    kwargs: dict[str, Any] = {k: v for k, v in ctx.obj.items() if v is not None}
    return build_client(**kwargs)


app.add_typer(auth.app, name="auth")
app.add_typer(bulk.app, name="bulk")
app.add_typer(company.app, name="company")
app.add_typer(contacts.app, name="contacts")
app.add_typer(discogen.app, name="discogen")
app.add_typer(email.app, name="email")
app.add_typer(queries.app, name="queries")
app.add_typer(account.app, name="account")
app.add_typer(providers.search_providers_app, name="search-providers")
app.add_typer(providers.llm_providers_app, name="llm-providers")
KEYBOARD_INTERRUPT_EXIT_CODE = 130


def run(argv: list[str] | None = None) -> None:
    """Console entry point: every failure, parser errors included, honours the JSON envelope.

    Click's standalone mode prints its own usage text on a bad flag or value; running the app
    with ``standalone_mode=False`` lets us route those through ``fail()`` so agents always see
    ``{"code": "validation_error", ...}`` on stderr with exit 2. Help, ``--version``, and the
    bare-invocation help screen keep click's behaviour.
    """
    try:
        result = app(args=argv, prog_name="discolike", standalone_mode=False)
    except NoArgsIsHelpError as exc:
        exc.show()
        sys.exit(exc.exit_code)
    except UsageError as exc:
        message = exc.format_message()
        if exc.ctx is not None:
            message = f"{message} (see `{exc.ctx.command_path} --help`)"
        sys.exit(fail(ValidationError(message)).exit_code)
    except ClickException as exc:
        exc.show()
        sys.exit(exc.exit_code)
    except (Abort, KeyboardInterrupt):
        sys.exit(KEYBOARD_INTERRUPT_EXIT_CODE)
    sys.exit(result if isinstance(result, int) else 0)


app.command(name="discover", cls=ContractCommand, epilog=epilog("discover"))(discover.discover_command)
app.command(name="count", cls=ContractCommand, epilog=epilog("count"))(discover.count_command)
app.command(name="match", cls=ContractCommand, epilog=epilog("match"))(match.match_command)
app.command(name="extract", cls=ContractCommand, epilog=epilog("extract"))(company.extract_command)
app.command(name="validate-icp", cls=ContractCommand, epilog=epilog("validate-icp"))(enrich.validate_icp_command)
app.command(name="append", cls=ContractCommand, epilog=epilog("append"))(enrich.append_command)
app.command(name="segment", cls=ContractCommand, epilog=epilog("segment"))(enrich.segment_command)
app.command(name="signup", cls=ContractCommand, epilog=epilog("signup"))(signup.signup_command)
