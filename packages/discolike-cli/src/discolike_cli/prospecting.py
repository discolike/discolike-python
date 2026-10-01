from __future__ import annotations

import json
import pathlib
import sys
import time
from typing import Any
from typing import Literal
from typing import NamedTuple
from uuid import uuid4

import typer

from discolike import CHECKPOINT_STOP_REASONS
from discolike import Discolike
from discolike import JobTimeoutError
from discolike.requests import ProspectingApproveRequest
from discolike.requests import ProspectingBrief
from discolike.requests import ProspectingGetParams
from discolike.requests import ProspectingListParams
from discolike.requests import ProspectingMessageRequest
from discolike.resources.prospecting import ProspectingMessage
from discolike.resources.prospecting import ProspectingRun
from discolike_cli._inputs import read_domains_file
from discolike_cli._output import NEEDS_INPUT_EXIT_CODE
from discolike_cli._output import build_request
from discolike_cli._output import emit
from discolike_cli._output import handle_errors
from discolike_cli.discover import _merge_params

app = typer.Typer(help="Run managed prospecting; processing and provider charges apply.")

AUTO_HELP = "Never pause to ask: a poor pilot is sharpened once and the run continues; it only stops if the re-pilot fit is still under 20%. A top_up round that would pass a spending limit still asks. Default: pause at checkpoints."
DELIVERABLE_HELP = "leads (default) finds people at the companies; accounts returns the checked companies only."
GOAL_HELP = (
    "leads (default) keeps adding rounds until the target is met; companies works only --target-companies "
    "matching companies."
)
CUSTOMERS_FILE_HELP = (
    "Your customers (CSV with a 'domain' column, or one per line): grouped into segments, lookalikes of each are "
    "found. Not with --domain or --company-name."
)
SEED_SEGMENT_HELP = (
    "A customer segment id from the plan card to expand (repeatable); omitted keeps the card's selection."
)
RESULTS_SEGMENT_HELP = "Group the finished results into segments; omitted keeps the brief's setting."
NO_INPUT_HELP = f"Never prompt: at a checkpoint, print the question and exit {NEEDS_INPUT_EXIT_CODE}."
NEEDS_INPUT_CODE = "needs_input"
WAIT_HELP = (
    "Return the first page on proposed, needs_input, completed, failed, or cancelled. Approve proposed plans; "
    "timeout stops polling only.\n\n"
    "At a checkpoint (stop_reason pilot, tail_quality, short, target_reached or top_up) a terminal shows the question, "
    "any sample companies and numbered replies, sends your pick or your own text, and keeps waiting. Without a "
    "terminal, or with --no-input, it prints the run on stdout and a needs_input envelope with the question and "
    f"suggested_replies on stderr, then exits {NEEDS_INPUT_EXIT_CODE}; answer with `prospecting message --text "
    "<reply>` and wait again."
)
TIMEOUT_MESSAGE = "Timed out waiting for prospecting; the run continues on the server"


class Pause(NamedTuple):
    question: str | None
    suggested_replies: list[str]
    sample: list[dict[str, Any]]


def _checkpoints(*, auto: bool) -> Literal["ask", "auto"]:
    return "auto" if auto else "ask"


def _is_interactive() -> bool:
    return sys.stdin.isatty()


def _at_checkpoint(run: ProspectingRun) -> bool:
    return run.status == "needs_input" and run.stop_reason in CHECKPOINT_STOP_REASONS


def _latest_question(client: Discolike, run: ProspectingRun) -> ProspectingMessage | None:
    """The run's newest question, paging past the first page of messages when there are more."""
    messages = list(run.messages)
    cursor = run.next_message_seq
    while page := client.prospecting.get(run.run_id, ProspectingGetParams(limit=1, messages_after=cursor)).messages:
        messages.extend(page)
        cursor = page[-1].seq
    return next((message for message in reversed(messages) if message.kind == "question"), None)


def _pause(run: ProspectingRun, question: ProspectingMessage | None) -> Pause:
    data = (question.data if question else None) or {}
    return Pause(
        question=question.content if question else run.error,
        suggested_replies=list(data.get("suggested_replies", [])),
        sample=list(data.get("sample", [])),
    )


def _report_pause(run: ProspectingRun, pause: Pause) -> typer.Exit:
    emit(run)
    envelope = {
        "error": "NeedsInput",
        "code": NEEDS_INPUT_CODE,
        "message": pause.question,
        "status_code": None,
        "exit_code": NEEDS_INPUT_EXIT_CODE,
        "run_id": str(run.run_id),
        "stop_reason": run.stop_reason,
        "suggested_replies": pause.suggested_replies,
        "sample": pause.sample,
    }
    print(json.dumps(envelope, default=str), file=sys.stderr)
    return typer.Exit(code=NEEDS_INPUT_EXIT_CODE)


def _ask(pause: Pause) -> str:
    if pause.question:
        typer.echo(pause.question, err=True)
    for company in pause.sample:
        reason = company.get("reason")
        typer.echo(f"  {company.get('domain')}: {reason}" if reason else f"  {company.get('domain')}", err=True)
    replies = pause.suggested_replies
    for number, reply in enumerate(replies, start=1):
        typer.echo(f"  {number}. {reply}", err=True)
    while True:
        answer = typer.prompt("Pick a number or type your answer", err=True).strip()
        if answer.isdigit() and 1 <= int(answer) <= len(replies):
            return replies[int(answer) - 1]
        if answer and not answer.isdigit():
            return answer


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise JobTimeoutError(TIMEOUT_MESSAGE)
    return remaining


def _await_reply(client: Discolike, *, run_id: str, after: int, deadline: float, poll_interval: float) -> None:
    """Poll until the agent has answered the message at seq `after`, then print its reply."""
    while True:
        run = client.prospecting.get(run_id, ProspectingGetParams(limit=1, messages_after=after))
        if not run.reply_pending:
            for message in run.messages:
                if message.role == "agent":
                    typer.echo(message.content, err=True)
            return
        time.sleep(min(poll_interval, _remaining(deadline)))


def _wait_answering(
    client: Discolike, *, run_id: str, timeout: float, poll_interval: float, no_input: bool
) -> ProspectingRun:
    deadline = time.monotonic() + timeout
    while True:
        run = client.prospecting.wait(run_id, max_wait=_remaining(deadline), poll_interval=poll_interval)
        if not _at_checkpoint(run):
            return run
        pause = _pause(run, _latest_question(client, run))
        if no_input or not _is_interactive():
            raise _report_pause(run, pause)
        sent = client.prospecting.message(
            run_id, ProspectingMessageRequest(text=_ask(pause)), idempotency_key=f"cli-checkpoint-{uuid4()}"
        )
        _await_reply(client, run_id=run_id, after=sent.seq, deadline=deadline, poll_interval=poll_interval)


@app.command("start")
@handle_errors
def start_command(
    ctx: typer.Context,
    brief: str = typer.Option(..., "--brief", help="Company criteria and buyer roles."),
    idempotency_key: str = typer.Option(..., "--idempotency-key", help="Reuse this key when retrying this submission."),
    domain: list[str] | None = typer.Option(None, "--domain", help="Starting domain (repeatable)."),
    company_name: list[str] | None = typer.Option(None, "--company-name", help="Company to match (repeatable)."),
    customers_file: pathlib.Path | None = typer.Option(None, "--customers-file", help=CUSTOMERS_FILE_HELP),
    exclude_domain: list[str] | None = typer.Option(None, "--exclude-domain", help="Suppressed domain (repeatable)."),
    target_companies: int | None = typer.Option(
        None,
        "--target-companies",
        min=1,
        max=10000,
        help="Override the company count in the brief; otherwise inferred, default 1000.",
    ),
    contacts_per_company: int | None = typer.Option(
        None,
        "--contacts-per-company",
        min=1,
        max=10,
        help="Override contacts per company; otherwise inferred, default 1.",
    ),
    max_candidates: int | None = typer.Option(
        None, "--max-candidates", min=0, max=100000, help="Candidate work cap; omitted or 0 means automatic."
    ),
    max_actions: int | None = typer.Option(
        None, "--max-actions", min=0, max=10000, help="Action work cap; omitted or 0 means automatic."
    ),
    validation_integration_id: str | None = typer.Option(None, "--validation-integration-id"),
    contact_integration_id: str | None = typer.Option(None, "--contact-integration-id"),
    search_provider_id: str | None = typer.Option(None, "--search-provider-id"),
    segment: bool = typer.Option(False, "--segment/--no-segment"),
    auto: bool = typer.Option(False, "--auto", help=AUTO_HELP),
    deliverable: str | None = typer.Option(None, "--deliverable", help=DELIVERABLE_HELP),
    goal: str | None = typer.Option(None, "--goal", help=GOAL_HELP),
) -> None:
    """Draft a plan. Wait for proposed, review it, then approve its plan version."""
    from discolike_cli.main import get_client

    request = build_request(
        ProspectingBrief,
        _merge_params(
            None,
            brief=brief,
            domains=domain,
            company_names=company_name,
            customer_domains=read_domains_file(customers_file) if customers_file is not None else None,
            exclude_domains=exclude_domain,
            target_companies=target_companies,
            contacts_per_company=contacts_per_company,
            max_candidates=max_candidates,
            max_actions=max_actions,
            validation_integration_id=validation_integration_id,
            contact_integration_id=contact_integration_id,
            search_provider_id=search_provider_id,
            segment=segment,
            checkpoints=_checkpoints(auto=auto),
            deliverable=deliverable,
            goal=goal,
        ),
    )
    emit(get_client(ctx).prospecting.start(request, idempotency_key=idempotency_key))


@app.command("status")
@handle_errors
def status_command(
    ctx: typer.Context,
    run_id: str = typer.Argument(...),
    offset: int = typer.Option(0, "--offset", min=0),
    limit: int = typer.Option(100, "--limit", min=1, max=500),
    events_after: int = typer.Option(0, "--events-after", min=0),
    messages_after: int = typer.Option(0, "--messages-after", min=0),
) -> None:
    """Retrieve status and one page of partial results."""
    from discolike_cli.main import get_client

    params = build_request(
        ProspectingGetParams,
        {"offset": offset, "limit": limit, "events_after": events_after, "messages_after": messages_after},
    )
    emit(get_client(ctx).prospecting.get(run_id, params))


@app.command("cancel")
@handle_errors
def cancel_command(ctx: typer.Context, run_id: str = typer.Argument(...)) -> None:
    """Stop new work; retain partial results and incurred charges."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).prospecting.cancel(run_id))


@app.command("wait", help=WAIT_HELP)
@handle_errors
def wait_command(
    ctx: typer.Context,
    run_id: str = typer.Argument(...),
    timeout: float = typer.Option(3600, "--timeout", min=0.01),
    poll_interval: float = typer.Option(5, "--poll-interval", min=5),
    no_input: bool = typer.Option(False, "--no-input", help=NO_INPUT_HELP),
) -> None:
    from discolike_cli.main import get_client

    emit(
        _wait_answering(get_client(ctx), run_id=run_id, timeout=timeout, poll_interval=poll_interval, no_input=no_input)
    )


@app.command("list")
@handle_errors
def list_command(
    ctx: typer.Context,
    limit: int = typer.Option(20, "--limit", min=1, max=50),
    before: str | None = typer.Option(None, "--before", help="Page past this run ID (last run ID from a prior page)."),
) -> None:
    """List recent organization runs, newest first."""
    from discolike_cli.main import get_client

    emit(
        get_client(ctx).prospecting.list(
            build_request(ProspectingListParams, _merge_params(None, limit=limit, before=before))
        )
    )


@app.command("approve")
@handle_errors
def approve_command(
    ctx: typer.Context,
    run_id: str = typer.Argument(...),
    plan_version: int = typer.Option(..., "--plan-version", min=1),
    auto: bool = typer.Option(False, "--auto", help=AUTO_HELP),
    seed_segment: list[int] | None = typer.Option(None, "--seed-segment", help=SEED_SEGMENT_HELP),
    segment: bool | None = typer.Option(None, "--segment/--no-segment", help=RESULTS_SEGMENT_HELP),
) -> None:
    """Approve the reviewed plan version and start research."""
    from discolike_cli.main import get_client

    emit(
        get_client(ctx).prospecting.approve(
            run_id,
            build_request(
                ProspectingApproveRequest,
                _merge_params(
                    None,
                    plan_version=plan_version,
                    checkpoints=_checkpoints(auto=auto),
                    seed_segments=seed_segment,
                    segment=segment,
                ),
            ),
        )
    )


@app.command("message")
@handle_errors
def message_command(
    ctx: typer.Context,
    run_id: str = typer.Argument(...),
    text: str = typer.Option(..., "--text"),
    idempotency_key: str = typer.Option(..., "--idempotency-key", help="Reuse when retrying this message."),
) -> None:
    """Send steering or a clarification answer; poll status --messages-after for the reply."""
    from discolike_cli.main import get_client

    emit(
        get_client(ctx).prospecting.message(
            run_id, build_request(ProspectingMessageRequest, {"text": text}), idempotency_key=idempotency_key
        )
    )
