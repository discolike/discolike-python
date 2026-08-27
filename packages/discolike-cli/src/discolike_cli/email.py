from __future__ import annotations

import csv
import pathlib
import sys

import typer

from discolike._email import EmailBatch
from discolike._email import EmailBatchResults
from discolike._email import EmailJobResult
from discolike._exceptions import JobTimeoutError
from discolike.requests import FindEmailBatchRequest
from discolike.requests import FindEmailRequest
from discolike_cli._output import build_request
from discolike_cli._output import emit
from discolike_cli._output import handle_errors
from discolike_cli.discover import _merge_params

DEFAULT_WAIT_TIMEOUT_SECONDS = 900.0
MAX_BATCH_CONTACTS = 500
EMAIL_KINDS = ("find", "verify")
CSV_COLUMNS = ("first_name", "last_name", "domain")

FORMAT_HELP = "Output format: json or table (table auto-selected on a TTY; falls back to JSON for non-tabular data)."
WAIT_HELP = "Block until the job finishes, streaming progress to stderr."
TIMEOUT_HELP = "Max seconds to wait with --wait."
KIND_HELP = "Batch kind: find or verify (verify batches are created by the DiscoLike app)."

app = typer.Typer(
    help=(
        "Find work email addresses: submit single or batch find jobs, poll them, and fetch results. "
        "Only proven addresses bill; catch-all and pattern guesses are free."
    )
)


def _job_status_to_stderr(status: EmailJobResult) -> None:
    sys.stderr.write(f"status: {status.status}\n")


def _batch_progress_to_stderr(results: EmailBatchResults) -> None:
    sys.stderr.write(f"progress: {results.completed}/{results.total} completed, {results.failed} failed\n")


def _parse_contact(value: str) -> dict[str, str]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != len(CSV_COLUMNS) or not all(parts):
        raise typer.BadParameter(f'--contact must be "first_name,last_name,domain", got {value!r}')
    return dict(zip(CSV_COLUMNS, parts, strict=True))


def _read_contacts_file(contacts_file: pathlib.Path) -> list[dict[str, str]]:
    with contacts_file.open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = set(CSV_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise typer.BadParameter(f"--contacts-file is missing required CSV columns: {', '.join(sorted(missing))}")
        return [{column: (row.get(column) or "").strip() for column in CSV_COLUMNS} for row in reader]


def _fetch_batch_snapshot(batch: EmailBatch) -> EmailBatchResults:
    """Fetch the batch results once, whether or not the batch has finished."""
    snapshot: dict[str, EmailBatchResults] = {}
    try:
        return batch.results(timeout=0, on_poll=lambda results: snapshot.update(latest=results))
    except JobTimeoutError:
        return snapshot["latest"]


@app.command("find")
@handle_errors
def find_command(
    ctx: typer.Context,
    first_name: str = typer.Argument(..., help="First name of the person."),
    last_name: str = typer.Argument(..., help="Last name of the person."),
    domain: str = typer.Argument(..., help="Company domain to search, e.g. acme.com."),
    known_pattern: str | None = typer.Option(
        None, "--known-pattern", help="Known email local-part pattern for this domain, e.g. first.last."
    ),
    wait: bool = typer.Option(False, "--wait/--no-wait", help=WAIT_HELP),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout", help=TIMEOUT_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Submit a single email find job (async); only a proven address bills."""
    from discolike_cli.main import get_client

    request = build_request(
        FindEmailRequest,
        _merge_params(None, first_name=first_name, last_name=last_name, domain=domain, known_pattern=known_pattern),
    )
    job = get_client(ctx).email.find(request)
    if not wait:
        emit({"job_id": job.job_id, "hint": f"poll with: discolike email job {job.job_id}"})
        return
    emit(job.wait(timeout=timeout, on_poll=_job_status_to_stderr), fmt=fmt)


@app.command("find-batch")
@handle_errors
def find_batch_command(
    ctx: typer.Context,
    contacts_file: pathlib.Path | None = typer.Option(
        None,
        "--contacts-file",
        help="Path to a CSV file with first_name,last_name,domain columns (max 500 contacts per batch).",
    ),
    contact: list[str] | None = typer.Option(
        None, "--contact", help='Inline contact as "first_name,last_name,domain" (repeatable).'
    ),
    wait: bool = typer.Option(False, "--wait/--no-wait", help=WAIT_HELP),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout", help=TIMEOUT_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Submit an email find batch from a CSV file and/or inline contacts (async)."""
    from discolike_cli.main import get_client

    contacts: list[dict[str, str]] = []
    if contacts_file is not None:
        contacts.extend(_read_contacts_file(contacts_file))
    contacts.extend(_parse_contact(value) for value in contact or [])
    if not contacts:
        raise typer.BadParameter("provide --contacts-file and/or at least one --contact")
    if len(contacts) > MAX_BATCH_CONTACTS:
        raise typer.BadParameter(f"a batch holds at most {MAX_BATCH_CONTACTS} contacts, got {len(contacts)}")

    batch = get_client(ctx).email.find_batch(build_request(FindEmailBatchRequest, {"requests": contacts}))
    if not wait:
        emit({"batch_id": batch.batch_id, "hint": f"fetch with: discolike email results {batch.batch_id}"})
        return
    emit(batch.results(timeout=timeout, on_poll=_batch_progress_to_stderr), fmt=fmt)


@app.command("results")
@handle_errors
def results_command(
    ctx: typer.Context,
    batch_id: str = typer.Argument(..., help="Batch ID returned by `discolike email find-batch`."),
    kind: str = typer.Option("find", "--kind", help=KIND_HELP),
    wait: bool = typer.Option(False, "--wait/--no-wait", help=WAIT_HELP),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout", help=TIMEOUT_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Fetch results for an email find or verify batch."""
    from discolike_cli.main import get_client

    if kind not in EMAIL_KINDS:
        raise typer.BadParameter(f"--kind must be one of: {', '.join(EMAIL_KINDS)}")
    batch = get_client(ctx).email.batch(batch_id, kind=kind)  # type: ignore[arg-type]
    if wait:
        emit(batch.results(timeout=timeout, on_poll=_batch_progress_to_stderr), fmt=fmt)
        return
    emit(_fetch_batch_snapshot(batch), fmt=fmt)


@app.command("job")
@handle_errors
def job_command(
    ctx: typer.Context,
    job_id: str = typer.Argument(..., help="Job ID returned by `discolike email find`."),
    wait: bool = typer.Option(False, "--wait/--no-wait", help=WAIT_HELP),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout", help=TIMEOUT_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Poll a single email find job: print its current status, or block with --wait."""
    from discolike_cli.main import get_client

    job = get_client(ctx).email.job(job_id)
    if wait:
        emit(job.wait(timeout=timeout, on_poll=_job_status_to_stderr), fmt=fmt)
        return
    emit(job.status(), fmt=fmt)
