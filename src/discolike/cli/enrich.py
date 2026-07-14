from __future__ import annotations

import pathlib

import typer

from discolike.cli._output import emit
from discolike.cli._output import handle_errors
from discolike.cli._output import run_job

DEFAULT_WAIT_TIMEOUT_SECONDS = 900.0


@handle_errors
def validate_icp_command(
    ctx: typer.Context,
    icp: str = typer.Option(..., "--icp"),
    domain: list[str] | None = typer.Option(None, "--domain"),
    file: pathlib.Path | None = typer.Option(None, "--file"),
    context_mode: str | None = typer.Option(None, "--context-mode"),
    integration_id: str | None = typer.Option(None, "--integration-id"),
    web_search: bool = typer.Option(False, "--web-search"),
    search_provider_id: str | None = typer.Option(None, "--search-provider-id"),
    wait: bool = typer.Option(False, "--wait"),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout"),
) -> None:
    from discolike.cli.main import get_client

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
    run_job(job, wait=wait, timeout=timeout)


@handle_errors
def append_command(
    ctx: typer.Context,
    file: pathlib.Path = typer.Argument(...),
    dataset: list[str] | None = typer.Option(None, "--dataset"),
    domain_column: str | None = typer.Option(None, "--domain-column"),
    csv: bool | None = typer.Option(None, "--csv/--no-csv"),
    output: pathlib.Path | None = typer.Option(None, "--output"),
) -> None:
    from discolike.cli.main import get_client

    result = get_client(ctx).append(file=file, dataset=dataset, domain_column=domain_column, csv=csv)
    if isinstance(result, bytes):
        if output is None:
            raise typer.BadParameter("--output is required when the response is CSV bytes")
        output.write_bytes(result)
        emit({"written": str(output), "bytes": len(result)})
        return
    emit(result)


@handle_errors
def segment_command(
    ctx: typer.Context,
    domain: list[str] | None = typer.Option(None, "--domain"),
    file: pathlib.Path | None = typer.Option(None, "--file"),
    domain_column: str | None = typer.Option(None, "--domain-column"),
    max_segments: int | None = typer.Option(None, "--max-segments"),
    wait: bool = typer.Option(False, "--wait"),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout"),
) -> None:
    from discolike.cli.main import get_client

    if (not domain) == (file is None):
        raise typer.BadParameter("Provide exactly one of --domain or --file")

    job = get_client(ctx).segment(
        domains=domain or None,
        file=file,
        domain_column=domain_column,
        max_segments=max_segments,
    )
    run_job(job, wait=wait, timeout=timeout)
