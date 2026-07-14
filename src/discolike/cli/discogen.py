from __future__ import annotations

import enum

import typer

from discolike._jobs import Job
from discolike.cli._output import emit
from discolike.cli._output import handle_errors
from discolike.cli._output import run_job

DEFAULT_WAIT_TIMEOUT_SECONDS = 900.0

app = typer.Typer(help="Run DiscoGen research and manage async tasks")


class TaskFamily(str, enum.Enum):
    discogen = "discogen"
    bulkmatch = "bulkmatch"
    contactmatch = "contactmatch"
    segment = "segment"


@app.command("run")
@handle_errors
def run_command(
    ctx: typer.Context,
    query: str = typer.Option(..., "--query"),
    domain: list[str] = typer.Option(..., "--domain"),
    integration_id: str | None = typer.Option(None, "--integration-id"),
    web_search: bool | None = typer.Option(None, "--web-search/--no-web-search"),
    context_mode: str | None = typer.Option(None, "--context-mode"),
    include_x_search: bool = typer.Option(False, "--include-x-search"),
    search_provider_id: str | None = typer.Option(None, "--search-provider-id"),
    search_context_size: str | None = typer.Option(None, "--search-context-size"),
    wait: bool = typer.Option(False, "--wait"),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout"),
) -> None:
    from discolike.cli.main import get_client

    job = get_client(ctx).discogen.process(
        query=query,
        domains=domain,
        integration_id=integration_id,
        web_search=web_search,
        context_mode=context_mode,
        include_x_search=include_x_search,
        search_provider_id=search_provider_id,
        search_context_size=search_context_size,
    )
    run_job(job, wait=wait, timeout=timeout)


@app.command("run-personas")
@handle_errors
def run_personas_command(
    ctx: typer.Context,
    query: str = typer.Option(..., "--query"),
    persona_id: list[int] = typer.Option(..., "--persona-id"),
    integration_id: str | None = typer.Option(None, "--integration-id"),
    web_search: bool | None = typer.Option(None, "--web-search/--no-web-search"),
    context_mode: str | None = typer.Option(None, "--context-mode"),
    include_x_search: bool = typer.Option(False, "--include-x-search"),
    search_provider_id: str | None = typer.Option(None, "--search-provider-id"),
    search_context_size: str | None = typer.Option(None, "--search-context-size"),
    wait: bool = typer.Option(False, "--wait"),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout"),
) -> None:
    from discolike.cli.main import get_client

    job = get_client(ctx).discogen.process_personas(
        query=query,
        persona_ids=persona_id,
        integration_id=integration_id,
        web_search=web_search,
        context_mode=context_mode,
        include_x_search=include_x_search,
        search_provider_id=search_provider_id,
        search_context_size=search_context_size,
    )
    run_job(job, wait=wait, timeout=timeout)


@app.command("models")
@handle_errors
def models_command(ctx: typer.Context) -> None:
    from discolike.cli.main import get_client

    emit(get_client(ctx).discogen.models())


def _build_job(ctx: typer.Context, family: TaskFamily, task_id: str) -> Job:
    from discolike.cli.main import get_client

    client = get_client(ctx)
    if family is TaskFamily.discogen:
        return client.discogen.job(task_id)
    return Job(client._transport, task_family=family.value, task_id=task_id)


@app.command("status")
@handle_errors
def status_command(
    ctx: typer.Context,
    task_id: str = typer.Argument(...),
    family: TaskFamily = typer.Option(TaskFamily.discogen, "--family"),
) -> None:
    emit(_build_job(ctx, family, task_id).status())


@app.command("cancel")
@handle_errors
def cancel_command(
    ctx: typer.Context,
    task_id: str = typer.Argument(...),
    family: TaskFamily = typer.Option(TaskFamily.discogen, "--family"),
) -> None:
    _build_job(ctx, family, task_id).cancel()
    emit({"cancelled": task_id})
