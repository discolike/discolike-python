from __future__ import annotations

import enum

import typer

from discolike._jobs import Job
from discolike.requests import DiscoGenPersonaProcessRequest
from discolike.requests import DiscoGenProcessRequest
from discolike_cli._output import build_request
from discolike_cli._output import emit
from discolike_cli._output import handle_errors
from discolike_cli._output import run_job
from discolike_cli.discover import _merge_params

DEFAULT_WAIT_TIMEOUT_SECONDS = 900.0

FORMAT_HELP = "Output format: json or table (table auto-selected on a TTY; falls back to JSON for non-tabular data)."
WAIT_HELP = "Block until the job finishes, streaming progress to stderr."
TIMEOUT_HELP = "Max seconds to wait with --wait."
FAMILY_HELP = (
    "Task family the task_id belongs to (bulk match jobs are 'bulkmatch', "
    "segment jobs 'segment', contact bulk-match 'contactmatch')."
)
QUERY_HELP = "Research query to run."
INTEGRATION_ID_HELP = "Integration ID to use for the run."
WEB_SEARCH_HELP = "Toggle web search during research."
CONTEXT_MODE_HELP = "Context mode; see docs.discolike.com."
INCLUDE_X_SEARCH_HELP = "Toggle including X search in the research."
SEARCH_PROVIDER_ID_HELP = "Search provider ID to use for web search."
SEARCH_CONTEXT_SIZE_HELP = "Search context size; see docs.discolike.com."
TASK_ID_HELP = "Task ID returned when the job was started."

app = typer.Typer(help="Run DiscoGen research jobs and check status of or cancel any async task (see --family)")


class TaskFamily(str, enum.Enum):
    discogen = "discogen"
    bulkmatch = "bulkmatch"
    contactmatch = "contactmatch"
    segment = "segment"


@app.command("run")
@handle_errors
def run_command(
    ctx: typer.Context,
    query: str = typer.Option(..., "--query", help=QUERY_HELP),
    domain: list[str] = typer.Option(..., "--domain", help="Company domain to research (repeatable)."),
    integration_id: str | None = typer.Option(None, "--integration-id", help=INTEGRATION_ID_HELP),
    web_search: bool | None = typer.Option(None, "--web-search/--no-web-search", help=WEB_SEARCH_HELP),
    context_mode: str | None = typer.Option(None, "--context-mode", help=CONTEXT_MODE_HELP),
    include_x_search: bool | None = typer.Option(
        None, "--include-x-search/--no-include-x-search", help=INCLUDE_X_SEARCH_HELP
    ),
    search_provider_id: str | None = typer.Option(None, "--search-provider-id", help=SEARCH_PROVIDER_ID_HELP),
    search_context_size: str | None = typer.Option(None, "--search-context-size", help=SEARCH_CONTEXT_SIZE_HELP),
    wait: bool = typer.Option(False, "--wait", help=WAIT_HELP),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout", help=TIMEOUT_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Run a DiscoGen research query across company domains (async job)."""
    from discolike_cli.main import get_client

    request = build_request(
        DiscoGenProcessRequest,
        _merge_params(
            None,
            query=query,
            domains=domain,
            integration_id=integration_id,
            web_search=web_search,
            context_mode=context_mode,
            include_x_search=include_x_search,
            search_provider_id=search_provider_id,
            search_context_size=search_context_size,
        ),
    )
    run_job(get_client(ctx).discogen.process(request), wait=wait, timeout=timeout, fmt=fmt)


@app.command("run-personas")
@handle_errors
def run_personas_command(
    ctx: typer.Context,
    query: str = typer.Option(..., "--query", help=QUERY_HELP),
    persona_id: list[int] = typer.Option(..., "--persona-id", help="Persona ID to research (repeatable)."),
    integration_id: str | None = typer.Option(None, "--integration-id", help=INTEGRATION_ID_HELP),
    web_search: bool | None = typer.Option(None, "--web-search/--no-web-search", help=WEB_SEARCH_HELP),
    context_mode: str | None = typer.Option(None, "--context-mode", help=CONTEXT_MODE_HELP),
    include_x_search: bool | None = typer.Option(
        None, "--include-x-search/--no-include-x-search", help=INCLUDE_X_SEARCH_HELP
    ),
    search_provider_id: str | None = typer.Option(None, "--search-provider-id", help=SEARCH_PROVIDER_ID_HELP),
    search_context_size: str | None = typer.Option(None, "--search-context-size", help=SEARCH_CONTEXT_SIZE_HELP),
    wait: bool = typer.Option(False, "--wait", help=WAIT_HELP),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout", help=TIMEOUT_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Run a DiscoGen research query across personas (async job)."""
    from discolike_cli.main import get_client

    request = build_request(
        DiscoGenPersonaProcessRequest,
        _merge_params(
            None,
            query=query,
            persona_ids=persona_id,
            integration_id=integration_id,
            web_search=web_search,
            context_mode=context_mode,
            include_x_search=include_x_search,
            search_provider_id=search_provider_id,
            search_context_size=search_context_size,
        ),
    )
    run_job(get_client(ctx).discogen.process_personas(request), wait=wait, timeout=timeout, fmt=fmt)


@app.command("models")
@handle_errors
def models_command(
    ctx: typer.Context,
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """List the models available for DiscoGen research."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).discogen.models(), fmt=fmt)


def _build_job(ctx: typer.Context, family: TaskFamily, task_id: str) -> Job:
    from discolike_cli.main import get_client

    client = get_client(ctx)
    if family is TaskFamily.discogen:
        return client.discogen.job(task_id)
    return Job(client._transport, task_family=family.value, task_id=task_id)


@app.command("status")
@handle_errors
def status_command(
    ctx: typer.Context,
    task_id: str = typer.Argument(..., help=TASK_ID_HELP),
    family: TaskFamily = typer.Option(TaskFamily.discogen, "--family", help=FAMILY_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Show the status and progress of an async task."""
    emit(_build_job(ctx, family, task_id).status(), fmt=fmt)


@app.command("cancel")
@handle_errors
def cancel_command(
    ctx: typer.Context,
    task_id: str = typer.Argument(..., help=TASK_ID_HELP),
    family: TaskFamily = typer.Option(TaskFamily.discogen, "--family", help=FAMILY_HELP),
) -> None:
    """Cancel an async task."""
    _build_job(ctx, family, task_id).cancel()
    emit({"cancelled": task_id})
