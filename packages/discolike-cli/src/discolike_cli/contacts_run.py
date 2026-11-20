from __future__ import annotations

import pathlib

import typer

from discolike.requests import ContactsRunEventsParams
from discolike.requests import ContactsRunGetParams
from discolike.requests import ContactsRunListParams
from discolike.requests import ContactsRunRequest
from discolike.requests import ContinueRunRequest
from discolike_cli._output import build_request
from discolike_cli._output import emit
from discolike_cli._output import handle_errors
from discolike_cli.discover import _merge_params

DEFAULT_WAIT_TIMEOUT_SECONDS = 3600.0

FORMAT_HELP = "Output format: json or table (table auto-selected on a TTY; falls back to JSON for non-tabular data)."
PARAMS_FILE_HELP = (
    "JSON object with the run request: companies (source prompt, domains or lookalike), relevance, "
    "people.fit, max_companies, per_company, email_cap_usd, exclusions and create_key. --param and flags override its values."
)
PARAM_HELP = "Extra key=value body field (repeatable)."
EMAIL_CAP_HELP = "Maximum USD to spend on validated delivery; omit for no cap."
LINKEDIN_ONLY_HELP = (
    "Also deliver people whose email could not be verified, with their LinkedIn profile and no email, "
    "at 1 record each. They count toward max_companies."
)
GENERATION_HELP = "Generation of the companies run you are continuing; fetched when omitted."

app = typer.Typer(help="Find and validate contacts automatically. Poll company progress and delivery totals.")


@app.command("create")
@handle_errors
def create_command(
    ctx: typer.Context,
    params_file: pathlib.Path | None = typer.Option(None, help=PARAMS_FILE_HELP),
    param: list[str] | None = typer.Option(None, "--param", help=PARAM_HELP),
    email_cap_usd: float | None = typer.Option(None, "--email-cap-usd", help=EMAIL_CAP_HELP),
    include_linkedin_only: bool | None = typer.Option(
        None, "--include-linkedin-only/--no-include-linkedin-only", help=LINKEDIN_ONLY_HELP
    ),
) -> None:
    """Start a contacts run from a JSON request."""
    from discolike_cli.main import get_client

    request = build_request(
        ContactsRunRequest,
        _merge_params(param, params_file, email_cap_usd=email_cap_usd, include_linkedin_only=include_linkedin_only),
    )
    emit(get_client(ctx).contacts_run.create(request))


@app.command("list")
@handle_errors
def list_command(
    ctx: typer.Context,
    before: str | None = typer.Option(
        None, help="Only runs created before this time, ISO 8601 with offset, e.g. 2026-10-30T12:00:00Z."
    ),
    limit: int | None = typer.Option(None, help="Runs per page (default 20, maximum 100)."),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """List your runs, newest first."""
    from discolike_cli.main import get_client

    params = build_request(ContactsRunListParams, _merge_params(None, before=before, limit=limit))
    emit(get_client(ctx).contacts_run.list(params), fmt=fmt)


@app.command("get")
@handle_errors
def get_command(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID."),
    rows_offset: int | None = typer.Option(None, help="Company domains to skip for contacts runs."),
    rows_limit: int | None = typer.Option(
        None, help="Company domains per page for contacts runs (default 100, maximum 1000)."
    ),
    all_rows: bool = typer.Option(False, "--all-rows", help="Print every row of the run as a list instead."),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Show a run with a page of its rows."""
    from discolike_cli.main import get_client

    client = get_client(ctx)
    if all_rows:
        emit(client.contacts_run.rows(run_id), fmt=fmt)
        return
    params = build_request(ContactsRunGetParams, _merge_params(None, rows_offset=rows_offset, rows_limit=rows_limit))
    emit(client.contacts_run.get(run_id, params))


@app.command("continue")
@handle_errors
def continue_command(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID."),
    generation: int | None = typer.Option(None, help=GENERATION_HELP),
    redo: bool | None = typer.Option(None, "--redo/--no-redo", help="Run the current step again."),
) -> None:
    """Advance or redo a companies run. Contacts runs proceed automatically (409 here)."""
    from discolike_cli.main import get_client

    client = get_client(ctx)
    request = build_request(
        ContinueRunRequest,
        _merge_params(
            None,
            generation=client.contacts_run.get(run_id).generation if generation is None else generation,
            redo=redo,
        ),
    )
    emit(client.contacts_run.continue_(run_id, request))


@app.command("cancel")
@handle_errors
def cancel_command(ctx: typer.Context, run_id: str = typer.Argument(..., help="Run ID.")) -> None:
    """Cancel a run; charges already incurred stay."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).contacts_run.cancel(run_id))


@app.command("wait")
@handle_errors
def wait_command(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID."),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout", help="Max seconds to wait."),
) -> None:
    """Block until done, failed or cancelled. A timeout stops local polling only."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).contacts_run.wait(run_id, max_wait=timeout))


@app.command("events")
@handle_errors
def events_command(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID."),
    after: int | None = typer.Option(None, help="Return events after this cursor."),
    limit: int | None = typer.Option(None, help="Events per page (default 100, maximum 500)."),
    tail: bool = typer.Option(False, "--tail", help="Return the newest page instead of reading from --after."),
) -> None:
    """Read company progress events and the next cursor."""
    from discolike_cli.main import get_client

    params = build_request(ContactsRunEventsParams, _merge_params(None, after=after, limit=limit, tail=tail or None))
    emit(get_client(ctx).contacts_run.events(run_id, params))
