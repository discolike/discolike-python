from __future__ import annotations

import pathlib

import typer

from discolike.cli._output import emit
from discolike.cli._output import handle_errors
from discolike.cli._output import run_job

DEFAULT_WAIT_TIMEOUT_SECONDS = 900.0
DEFAULT_NAME_COLUMN = "name"


@handle_errors
def match_command(
    ctx: typer.Context,
    name: str | None = typer.Argument(None),
    phone: str | None = typer.Option(None),
    city: str | None = typer.Option(None),
    state: str | None = typer.Option(None),
    country: str | None = typer.Option(None),
    zip_code: str | None = typer.Option(None),
    strict: bool | None = typer.Option(None, "--strict/--no-strict"),
    local_mode: bool | None = typer.Option(None, "--local-mode/--no-local-mode"),
    file: pathlib.Path | None = typer.Option(None, "--file"),
    name_column: str = typer.Option(DEFAULT_NAME_COLUMN, "--name-column"),
    wait: bool = typer.Option(False, "--wait"),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout"),
    fmt: str | None = typer.Option(None, "--format"),
) -> None:
    from discolike.cli.main import get_client

    if (name is None) == (file is None):
        raise typer.BadParameter("Provide exactly one of NAME or --file")

    client = get_client(ctx)
    if name is not None:
        response = client.match.company(
            name=name,
            phone=phone,
            city=city,
            state=state,
            country=country,
            zip_code=zip_code,
            strict=strict,
            local_mode=local_mode,
        )
        emit(response, fmt=fmt)
        return

    assert file is not None
    job = client.match.bulk(file=file, name_column=name_column, strict=strict, local_mode=local_mode)
    run_job(job, wait=wait, timeout=timeout)
