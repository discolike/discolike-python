from __future__ import annotations

import csv
import json
from pathlib import Path

import typer

from discolike_cli._output import emit
from discolike_cli._output import handle_errors

FORMAT_HELP = "Output format: json or table (table auto-selected on a TTY; falls back to JSON for non-tabular data)."

app = typer.Typer(help="Manage saved queries and exclusion lists for reusable targeting.")


@app.command("list")
@handle_errors
def list_command(
    ctx: typer.Context,
    max_records: int | None = typer.Option(None, "--max-records", help="Maximum number of saved queries to return."),
    offset: int | None = typer.Option(None, "--offset", help="Number of records to skip for pagination."),
    action: str | None = typer.Option(None, "--action", help="Filter by query action, e.g. discover"),
    tag: list[str] | None = typer.Option(None, "--tag", help="Filter by tag (repeatable)."),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """List saved queries."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).queries.list(max_records=max_records, offset=offset, action=action, tags=tag), fmt=fmt)


@app.command("create-exclusion-list")
@handle_errors
def create_exclusion_list_command(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", help="Name for the new exclusion list."),
    domain: list[str] | None = typer.Option(None, "--domain", help="Domain to exclude (repeatable)."),
    persona_id: list[int] | None = typer.Option(None, "--persona-id", help="Persona ID to exclude (repeatable)."),
    tag: list[str] | None = typer.Option(None, "--tag", help="Tag to attach to the list (repeatable)."),
) -> None:
    """Create a named exclusion list of domains and/or persona IDs."""
    from discolike_cli.main import get_client

    emit(
        get_client(ctx).queries.create_exclusion_list(
            query_name=name,
            domains=domain,
            persona_ids=persona_id,
            tags=tag,
        )
    )


@app.command("save-results")
@handle_errors
def save_results_command(
    ctx: typer.Context,
    input_path: Path = typer.Option(
        ..., "--input", help="Path to a .json (list of row objects) or .csv (header row) file."
    ),
    name: str = typer.Option(..., "--name", help="Name for the saved query."),
    action: str = typer.Option(
        ..., "--action", help="Underlying action: discover, segment, contacts, append, or match."
    ),
    domain_column: str = typer.Option("domain", "--domain-column", help="Column holding domains."),
    tag: list[str] | None = typer.Option(None, "--tag", help="Tag to attach (repeatable)."),
) -> None:
    """Save result rows from a file as a reusable saved query."""
    from discolike_cli.main import get_client

    try:
        if input_path.suffix.lower() == ".csv":
            with input_path.open(newline="") as fh:
                data = [dict(row) for row in csv.DictReader(fh)]
        else:
            data = json.loads(input_path.read_text())
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"--input file not found: {input_path}") from exc
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"--input file {input_path} must contain valid JSON: {exc}") from exc

    emit(
        get_client(ctx).queries.save_results(
            query_name=name,
            action=action,
            data=data,
            domain_column=domain_column,
            tags=tag,
        )
    )


@app.command("update")
@handle_errors
def update_command(
    ctx: typer.Context,
    query_id: str = typer.Argument(..., help="ID of the saved query to update."),
    name: str | None = typer.Option(None, "--name", help="New name for the saved query."),
    tag: list[str] | None = typer.Option(None, "--tag", help="Tag to set on the query (repeatable)."),
) -> None:
    """Rename a saved query and/or update its tags."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).queries.update(query_id=query_id, query_name=name, tags=tag))


@app.command("delete")
@handle_errors
def delete_command(
    ctx: typer.Context,
    query_id: str = typer.Argument(..., help="ID of the saved query to delete."),
) -> None:
    """Delete a saved query."""
    from discolike_cli.main import get_client

    get_client(ctx).queries.delete(query_id=query_id)
    emit({"deleted": query_id})
