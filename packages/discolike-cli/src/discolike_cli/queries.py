from __future__ import annotations

import typer

from discolike_cli._output import emit
from discolike_cli._output import handle_errors

app = typer.Typer(help="Manage saved queries and exclusion lists")


@app.command("list")
@handle_errors
def list_command(
    ctx: typer.Context,
    max_records: int | None = typer.Option(None, "--max-records"),
    offset: int | None = typer.Option(None, "--offset"),
    action: str | None = typer.Option(None, "--action"),
    tag: list[str] | None = typer.Option(None, "--tag"),
) -> None:
    from discolike_cli.main import get_client

    emit(get_client(ctx).queries.list(max_records=max_records, offset=offset, action=action, tags=tag))


@app.command("create-exclusion-list")
@handle_errors
def create_exclusion_list_command(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name"),
    domain: list[str] | None = typer.Option(None, "--domain"),
    persona_id: list[int] | None = typer.Option(None, "--persona-id"),
    tag: list[str] | None = typer.Option(None, "--tag"),
) -> None:
    from discolike_cli.main import get_client

    emit(
        get_client(ctx).queries.create_exclusion_list(
            query_name=name,
            domains=domain,
            persona_ids=persona_id,
            tags=tag,
        )
    )


@app.command("update")
@handle_errors
def update_command(
    ctx: typer.Context,
    query_id: str = typer.Argument(...),
    name: str | None = typer.Option(None, "--name"),
    tag: list[str] | None = typer.Option(None, "--tag"),
) -> None:
    from discolike_cli.main import get_client

    emit(get_client(ctx).queries.update(query_id=query_id, query_name=name, tags=tag))


@app.command("delete")
@handle_errors
def delete_command(ctx: typer.Context, query_id: str = typer.Argument(...)) -> None:
    from discolike_cli.main import get_client

    get_client(ctx).queries.delete(query_id=query_id)
    emit({"deleted": query_id})
