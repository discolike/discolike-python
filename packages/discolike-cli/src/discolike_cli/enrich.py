from __future__ import annotations

import pathlib

import typer

from discolike_cli._output import emit
from discolike_cli._output import handle_errors
from discolike_cli._output import run_job

DEFAULT_WAIT_TIMEOUT_SECONDS = 900.0

FORMAT_HELP = "Output format: json or table (table auto-selected on a TTY; falls back to JSON for non-tabular data)."
WAIT_HELP = "Block until the job finishes, streaming progress to stderr."
TIMEOUT_HELP = "Max seconds to wait with --wait."


@handle_errors
def validate_icp_command(
    ctx: typer.Context,
    icp: str = typer.Option(..., "--icp", help="ICP definition text to validate the domains against."),
    domain: list[str] | None = typer.Option(None, "--domain", help="Domain to validate (repeatable)."),
    file: pathlib.Path | None = typer.Option(
        None, "--file", help="Text file with one domain per line (instead of --domain)."
    ),
    context_mode: str | None = typer.Option(None, "--context-mode", help="Context mode; see docs.discolike.com."),
    integration_id: str | None = typer.Option(
        None, "--integration-id", help="Integration ID to use for the validation."
    ),
    web_search: bool | None = typer.Option(
        None, "--web-search/--no-web-search", help="Toggle web search during validation."
    ),
    search_provider_id: str | None = typer.Option(
        None, "--search-provider-id", help="Search provider ID to use for web search."
    ),
    wait: bool = typer.Option(False, "--wait", help=WAIT_HELP),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout", help=TIMEOUT_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Validate a list of domains against an ICP definition (async job)."""
    from discolike_cli.main import get_client

    if (not domain) == (file is None):
        raise typer.BadParameter("Provide exactly one of --domain or --file")

    if file is not None:
        domains = [line.strip() for line in file.read_text().splitlines() if line.strip()]
    else:
        assert domain is not None
        domains = domain

    job = get_client(ctx).validate_icp(
        icp_text=icp,
        domains=domains,
        context_mode=context_mode,
        integration_id=integration_id,
        web_search=web_search,
        search_provider_id=search_provider_id,
    )
    run_job(job, wait=wait, timeout=timeout, fmt=fmt)


@handle_errors
def append_command(
    ctx: typer.Context,
    file: pathlib.Path = typer.Argument(..., help="CSV of domains to enrich."),
    dataset: list[str] | None = typer.Option(None, "--dataset", help="Dataset to append (repeatable)."),
    domain_column: str | None = typer.Option(None, "--domain-column", help="Column in the CSV that holds domains."),
    csv: bool | None = typer.Option(
        None, "--csv/--no-csv", help="Request the enriched rows as CSV (written via --output)."
    ),
    output: pathlib.Path | None = typer.Option(None, "--output", help="File to write a CSV response to."),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Enrich a CSV of domains with DiscoLike datasets."""
    from discolike_cli.main import get_client

    result = get_client(ctx).append(file=file, dataset=dataset, domain_column=domain_column, csv=csv)
    if isinstance(result, bytes):
        if output is None:
            raise typer.BadParameter("--output is required when the response is CSV bytes")
        output.write_bytes(result)
        emit({"written": str(output), "bytes": len(result)})
        return
    emit(result, fmt=fmt)


@handle_errors
def segment_command(
    ctx: typer.Context,
    domain: list[str] | None = typer.Option(None, "--domain", help="Domain to segment (repeatable)."),
    file: pathlib.Path | None = typer.Option(None, "--file", help="CSV of domains to segment (instead of --domain)."),
    domain_column: str | None = typer.Option(None, "--domain-column", help="Column in --file that holds domains."),
    max_segments: int | None = typer.Option(None, "--max-segments", help="Maximum number of segments to produce."),
    wait: bool = typer.Option(False, "--wait", help=WAIT_HELP),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout", help=TIMEOUT_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Auto-segment a list of domains (async job)."""
    from discolike_cli.main import get_client

    if (not domain) == (file is None):
        raise typer.BadParameter("Provide exactly one of --domain or --file")

    job = get_client(ctx).segment(
        domains=domain or None,
        file=file,
        domain_column=domain_column,
        max_segments=max_segments,
    )
    run_job(job, wait=wait, timeout=timeout, fmt=fmt)
