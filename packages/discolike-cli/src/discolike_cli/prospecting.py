from __future__ import annotations

import typer

from discolike.requests import ProspectingApproveRequest
from discolike.requests import ProspectingBrief
from discolike.requests import ProspectingGetParams
from discolike.requests import ProspectingListParams
from discolike.requests import ProspectingMessageRequest
from discolike_cli._output import build_request
from discolike_cli._output import emit
from discolike_cli._output import handle_errors
from discolike_cli.discover import _merge_params

app = typer.Typer(help="Run managed prospecting; processing and provider charges apply.")


@app.command("start")
@handle_errors
def start_command(
    ctx: typer.Context,
    brief: str = typer.Option(..., "--brief", help="Company criteria and buyer roles."),
    idempotency_key: str = typer.Option(..., "--idempotency-key", help="Reuse this key when retrying this submission."),
    domain: list[str] | None = typer.Option(None, "--domain", help="Starting domain (repeatable)."),
    company_name: list[str] | None = typer.Option(None, "--company-name", help="Company to match (repeatable)."),
    exclude_domain: list[str] | None = typer.Option(None, "--exclude-domain", help="Suppressed domain (repeatable)."),
    target_companies: int | None = typer.Option(
        None,
        "--target-companies",
        min=1,
        max=10000,
        help="Override the company count in the brief; otherwise inferred, default 25.",
    ),
    contacts_per_company: int | None = typer.Option(
        None,
        "--contacts-per-company",
        min=1,
        max=5,
        help="Override contacts per company; otherwise inferred, default 2.",
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
            exclude_domains=exclude_domain,
            target_companies=target_companies,
            contacts_per_company=contacts_per_company,
            max_candidates=max_candidates,
            max_actions=max_actions,
            validation_integration_id=validation_integration_id,
            contact_integration_id=contact_integration_id,
            search_provider_id=search_provider_id,
            segment=segment,
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


@app.command("wait")
@handle_errors
def wait_command(
    ctx: typer.Context,
    run_id: str = typer.Argument(...),
    timeout: float = typer.Option(3600, "--timeout", min=0.01),
    poll_interval: float = typer.Option(5, "--poll-interval", min=5),
) -> None:
    """Return the first page on proposed, needs_input, completed, failed, or cancelled. Approve proposed plans; timeout stops polling only."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).prospecting.wait(run_id, timeout=timeout, poll_interval=poll_interval))


@app.command("list")
@handle_errors
def list_command(ctx: typer.Context, limit: int = typer.Option(20, "--limit", min=1, max=50)) -> None:
    """List recent organization runs, newest first."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).prospecting.list(build_request(ProspectingListParams, {"limit": limit})))


@app.command("approve")
@handle_errors
def approve_command(
    ctx: typer.Context,
    run_id: str = typer.Argument(...),
    plan_version: int = typer.Option(..., "--plan-version", min=1),
) -> None:
    """Approve the reviewed plan version and start research."""
    from discolike_cli.main import get_client

    emit(
        get_client(ctx).prospecting.approve(
            run_id, build_request(ProspectingApproveRequest, {"plan_version": plan_version})
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
