from __future__ import annotations

import typer

from discolike.requests import ProspectingBrief
from discolike.requests import ProspectingGetParams
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
    target_companies: int = typer.Option(25, "--target-companies", min=1, max=100),
    contacts_per_company: int = typer.Option(2, "--contacts-per-company", min=1, max=5),
    max_candidates: int = typer.Option(200, "--max-candidates", min=1, max=1000),
    max_actions: int = typer.Option(24, "--max-actions", min=1, max=60),
    validation_integration_id: str | None = typer.Option(None, "--validation-integration-id"),
    contact_integration_id: str | None = typer.Option(None, "--contact-integration-id"),
    search_provider_id: str | None = typer.Option(None, "--search-provider-id"),
    segment: bool = typer.Option(False, "--segment/--no-segment"),
) -> None:
    """Return a run ID immediately. Poll status or wait; limits bound work, not provider dollars."""
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
    limit: int = typer.Option(100, "--limit", min=1, max=100),
) -> None:
    """Retrieve status and one page of partial results."""
    from discolike_cli.main import get_client

    params = build_request(ProspectingGetParams, {"offset": offset, "limit": limit})
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
    """Return the first page on any terminal status. Inspect stop_reason; timeout leaves the run active."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).prospecting.wait(run_id, timeout=timeout, poll_interval=poll_interval))
