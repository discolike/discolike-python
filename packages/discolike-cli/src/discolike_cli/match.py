from __future__ import annotations

import pathlib

import typer

from discolike.requests import MatchBulkParams
from discolike.requests import MatchCompanyParams
from discolike_cli._output import build_request
from discolike_cli._output import emit
from discolike_cli._output import handle_errors
from discolike_cli._output import run_job
from discolike_cli.discover import _merge_params

DEFAULT_WAIT_TIMEOUT_SECONDS = 900.0
DEFAULT_NAME_COLUMN = "name"

FORMAT_HELP = "Output format: json or table (table auto-selected on a TTY; falls back to JSON for non-tabular data)."
WAIT_HELP = "Block until the job finishes, streaming progress to stderr."
TIMEOUT_HELP = "Max seconds to wait with --wait."


@handle_errors
def match_command(
    ctx: typer.Context,
    name: str | None = typer.Argument(None, help="Company name to match to a domain."),
    phone: str | None = typer.Option(None, help="Phone number to disambiguate the match."),
    city: str | None = typer.Option(None, help="City to disambiguate the match."),
    state: str | None = typer.Option(None, help="State or region to disambiguate the match."),
    country: str | None = typer.Option(None, help="Country to disambiguate the match."),
    zip_code: str | None = typer.Option(None, help="ZIP or postal code to disambiguate the match."),
    strict: bool | None = typer.Option(None, "--strict/--no-strict", help="Toggle strict matching."),
    local_mode: bool | None = typer.Option(None, "--local-mode/--no-local-mode", help="Toggle local matching mode."),
    file: pathlib.Path | None = typer.Option(
        None, "--file", help="CSV of company names to bulk-match as an async job (instead of NAME)."
    ),
    name_column: str = typer.Option(
        DEFAULT_NAME_COLUMN, "--name-column", help="Column in --file that holds company names."
    ),
    wait: bool = typer.Option(False, "--wait", help=WAIT_HELP),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout", help=TIMEOUT_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Match a company name to a domain, or bulk-match a CSV of names."""
    from discolike_cli.main import get_client

    if (name is None) == (file is None):
        raise typer.BadParameter("Provide exactly one of NAME or --file")

    client = get_client(ctx)
    if name is not None:
        request = build_request(
            MatchCompanyParams,
            _merge_params(
                None,
                name=name,
                phone=phone,
                city=city,
                state=state,
                country=country,
                zip_code=zip_code,
                strict=strict,
                local_mode=local_mode,
            ),
        )
        emit(client.match.company(request), fmt=fmt)
        return

    assert file is not None
    request = build_request(
        MatchBulkParams, _merge_params(None, name_column=name_column, strict=strict, local_mode=local_mode)
    )
    run_job(client.match.bulk(request, file=file), wait=wait, timeout=timeout, fmt=fmt)
