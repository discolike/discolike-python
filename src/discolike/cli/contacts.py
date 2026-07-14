from __future__ import annotations

import json
import pathlib

import typer

from discolike.cli._output import call_typed
from discolike.cli._output import emit
from discolike.cli._output import handle_errors
from discolike.cli._output import run_job
from discolike.cli.discover import _merge_params

DEFAULT_WAIT_TIMEOUT_SECONDS = 900.0

app = typer.Typer(help="Search, match, and enrich contacts")


@app.command("search")
@handle_errors
def search_command(
    ctx: typer.Context,
    icp_prompt: str | None = typer.Option(None),
    icp_text: str | None = typer.Option(None),
    seniority: list[str] | None = typer.Option(None),
    department: list[str] | None = typer.Option(None),
    title: list[str] | None = typer.Option(None),
    domain: list[str] | None = typer.Option(None),
    person_country: list[str] | None = typer.Option(None),
    filter_industry: list[str] | None = typer.Option(None),
    filter_country: list[str] | None = typer.Option(None),
    employee_range: str | None = typer.Option(None),
    has_email: bool | None = typer.Option(None, "--has-email/--no-has-email"),
    max_records: int | None = typer.Option(None),
    offset: int | None = typer.Option(None),
    fmt: str | None = typer.Option(None, "--format"),
    param: list[str] | None = typer.Option(None, "--param"),
) -> None:
    from discolike.cli.main import get_client

    kwargs = _merge_params(
        param,
        icp_prompt=icp_prompt,
        icp_text=icp_text,
        seniority=seniority,
        department=department,
        title=title,
        domain=domain,
        person_country=person_country,
        filter_industry=filter_industry,
        filter_country=filter_country,
        employee_range=employee_range,
        has_email=has_email,
        max_records=max_records,
        offset=offset,
    )
    emit(call_typed(get_client(ctx).contacts.search, **kwargs), fmt=fmt)


@app.command("count")
@handle_errors
def count_command(
    ctx: typer.Context,
    icp_prompt: str | None = typer.Option(None),
    icp_text: str | None = typer.Option(None),
    seniority: list[str] | None = typer.Option(None),
    department: list[str] | None = typer.Option(None),
    title: list[str] | None = typer.Option(None),
    domain: list[str] | None = typer.Option(None),
    person_country: list[str] | None = typer.Option(None),
    filter_industry: list[str] | None = typer.Option(None),
    filter_country: list[str] | None = typer.Option(None),
    employee_range: str | None = typer.Option(None),
    has_email: bool | None = typer.Option(None, "--has-email/--no-has-email"),
    fmt: str | None = typer.Option(None, "--format"),
    param: list[str] | None = typer.Option(None, "--param"),
) -> None:
    from discolike.cli.main import get_client

    kwargs = _merge_params(
        param,
        icp_prompt=icp_prompt,
        icp_text=icp_text,
        seniority=seniority,
        department=department,
        title=title,
        domain=domain,
        person_country=person_country,
        filter_industry=filter_industry,
        filter_country=filter_country,
        employee_range=employee_range,
        has_email=has_email,
    )
    emit(call_typed(get_client(ctx).contacts.count, **kwargs), fmt=fmt)


@app.command("lookup")
@handle_errors
def lookup_command(
    ctx: typer.Context,
    persona_id: int | None = typer.Option(None, "--persona-id"),
    linkedin: str | None = typer.Option(None, "--linkedin"),
    email: str | None = typer.Option(None, "--email"),
) -> None:
    from discolike.cli.main import get_client

    emit(get_client(ctx).contacts.lookup(persona_id=persona_id, linkedin=linkedin, email=email))


@app.command("match")
@handle_errors
def match_command(
    ctx: typer.Context,
    name: str = typer.Argument(...),
    company_name: str | None = typer.Option(None, "--company-name"),
    domain: str | None = typer.Option(None, "--domain"),
    person_country: str | None = typer.Option(None, "--person-country"),
    limit: int | None = typer.Option(None, "--limit"),
) -> None:
    from discolike.cli.main import get_client

    emit(
        get_client(ctx).contacts.match(
            name=name,
            company_name=company_name,
            domain=domain,
            person_country=person_country,
            limit=limit,
        )
    )


@app.command("bulk-match")
@handle_errors
def bulk_match_command(
    ctx: typer.Context,
    queries_file: pathlib.Path = typer.Option(..., "--queries-file"),
    enrich: bool | None = typer.Option(None, "--enrich/--no-enrich"),
    limit: int | None = typer.Option(None, "--limit"),
    wait: bool = typer.Option(False, "--wait"),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout"),
) -> None:
    from discolike.cli.main import get_client

    try:
        queries = json.loads(queries_file.read_text())
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"--queries-file must contain valid JSON: {exc}") from exc
    if not isinstance(queries, list):
        raise typer.BadParameter("--queries-file must contain a JSON array of objects")

    job = get_client(ctx).contacts.bulk_match(queries=queries, enrich=enrich, limit=limit)
    run_job(job, wait=wait, timeout=timeout)


@app.command("discover")
@handle_errors
def discover_command(
    ctx: typer.Context,
    icp_prompt: str | None = typer.Option(None),
    icp_text: str | None = typer.Option(None),
    seniority: list[str] | None = typer.Option(None),
    department: list[str] | None = typer.Option(None),
    title: list[str] | None = typer.Option(None),
    domain: list[str] | None = typer.Option(None),
    person_country: list[str] | None = typer.Option(None),
    filter_industry: list[str] | None = typer.Option(None),
    filter_country: list[str] | None = typer.Option(None),
    employee_range: str | None = typer.Option(None),
    has_email: bool | None = typer.Option(None, "--has-email/--no-has-email"),
    max_records: int | None = typer.Option(None),
    offset: int | None = typer.Option(None),
    results_by_company: int | None = typer.Option(None, "--results-by-company"),
    include_search_contacts: bool | None = typer.Option(None, "--include-search-contacts/--no-include-search-contacts"),
    consensus: int | None = typer.Option(None, "--consensus"),
    fmt: str | None = typer.Option(None, "--format"),
    param: list[str] | None = typer.Option(None, "--param"),
) -> None:
    from discolike.cli.main import get_client

    kwargs = _merge_params(
        param,
        icp_prompt=icp_prompt,
        icp_text=icp_text,
        seniority=seniority,
        department=department,
        title=title,
        domain=domain,
        person_country=person_country,
        filter_industry=filter_industry,
        filter_country=filter_country,
        employee_range=employee_range,
        has_email=has_email,
        max_records=max_records,
        offset=offset,
        results_by_company=results_by_company,
        include_search_contacts=include_search_contacts,
        consensus=consensus,
    )
    emit(call_typed(get_client(ctx).contacts.discover, **kwargs), fmt=fmt)


@app.command("generate")
@handle_errors
def generate_command(
    ctx: typer.Context,
    icp_text: str = typer.Option(..., "--icp-text"),
    domain: list[str] = typer.Option(..., "--domain"),
    context_mode: str | None = typer.Option(None, "--context-mode"),
    integration_id: str | None = typer.Option(None, "--integration-id"),
    search_provider_id: str | None = typer.Option(None, "--search-provider-id"),
    search_context_size: str | None = typer.Option(None, "--search-context-size"),
    max_contacts_per_domain: int | None = typer.Option(None, "--max-contacts-per-domain"),
    max_company_records: int | None = typer.Option(None, "--max-company-records"),
    wait: bool = typer.Option(False, "--wait"),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout"),
) -> None:
    from discolike.cli.main import get_client

    job = get_client(ctx).contacts.generate(
        icp_text=icp_text,
        domains=domain,
        context_mode=context_mode,
        integration_id=integration_id,
        search_provider_id=search_provider_id,
        search_context_size=search_context_size,
        max_contacts_per_domain=max_contacts_per_domain,
        max_company_records=max_company_records,
    )
    run_job(job, wait=wait, timeout=timeout)
