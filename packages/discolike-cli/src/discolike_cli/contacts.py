from __future__ import annotations

import json
import pathlib

import typer

from discolike_cli._output import call_typed
from discolike_cli._output import emit
from discolike_cli._output import handle_errors
from discolike_cli._output import run_job
from discolike_cli.discover import _merge_params

DEFAULT_WAIT_TIMEOUT_SECONDS = 900.0

FORMAT_HELP = "Output format: json or table (table auto-selected on a TTY; falls back to JSON for non-tabular data)."
WAIT_HELP = "Block until the job finishes, streaming progress to stderr."
TIMEOUT_HELP = "Max seconds to wait with --wait."
PARAM_HELP = "Extra key=value query parameter forwarded to the SDK (repeatable)."
JOBSTART_DATE_HELP = "Job start date filter: min date or 'min,max' range, e.g. 2025-01-01 or 2025-01-01,2025-06-30."

app = typer.Typer(
    help="Find contacts: search and count by filters, look up or match individuals, and run bulk/generative discovery jobs."
)


@app.command("search")
@handle_errors
def search_command(
    ctx: typer.Context,
    icp_prompt: str | None = typer.Option(None, help="Natural-language ICP prompt used to derive contact filters."),
    seniority: list[str] | None = typer.Option(None, help="Filter by seniority level (repeatable)."),
    negate_seniority: list[str] | None = typer.Option(None, help="Exclude seniority levels (repeatable)."),
    department: list[str] | None = typer.Option(None, help="Filter by department (repeatable)."),
    negate_department: list[str] | None = typer.Option(None, help="Exclude departments (repeatable)."),
    title: list[str] | None = typer.Option(None, help="Filter by job title (repeatable)."),
    negate_title: list[str] | None = typer.Option(None, help="Exclude job titles (repeatable)."),
    domain: list[str] | None = typer.Option(None, help="Filter by company domain (repeatable)."),
    person_country: list[str] | None = typer.Option(None, help="Filter by contact country (repeatable)."),
    negate_person_country: list[str] | None = typer.Option(None, help="Exclude contact countries (repeatable)."),
    filter_industry: list[str] | None = typer.Option(None, help="Filter by company industry (repeatable)."),
    negate_filter_industry: list[str] | None = typer.Option(None, help="Exclude company industries (repeatable)."),
    filter_country: list[str] | None = typer.Option(None, help="Filter by company country (repeatable)."),
    negate_filter_country: list[str] | None = typer.Option(None, help="Exclude company countries (repeatable)."),
    employee_range: str | None = typer.Option(None, help="Company employee range, e.g. 50-200."),
    has_email: bool | None = typer.Option(
        None, "--has-email/--no-has-email", help="Only contacts with (or without) an email address."
    ),
    jobstart_date: str | None = typer.Option(None, "--jobstart-date", help=JOBSTART_DATE_HELP),
    max_records: int | None = typer.Option(None, help="Maximum number of contacts to return."),
    offset: int | None = typer.Option(None, help="Number of records to skip for pagination."),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
    param: list[str] | None = typer.Option(None, "--param", help=PARAM_HELP),
) -> None:
    """Search contacts matching the given filters."""
    from discolike_cli.main import get_client

    kwargs = _merge_params(
        param,
        icp_prompt=icp_prompt,
        seniority=seniority,
        negate_seniority=negate_seniority,
        department=department,
        negate_department=negate_department,
        title=title,
        negate_title=negate_title,
        domain=domain,
        person_country=person_country,
        negate_person_country=negate_person_country,
        filter_industry=filter_industry,
        negate_filter_industry=negate_filter_industry,
        filter_country=filter_country,
        negate_filter_country=negate_filter_country,
        employee_range=employee_range,
        has_email=has_email,
        jobstart_date=jobstart_date,
        max_records=max_records,
        offset=offset,
    )
    emit(call_typed(get_client(ctx).contacts.search, **kwargs), fmt=fmt)


@app.command("count")
@handle_errors
def count_command(
    ctx: typer.Context,
    icp_prompt: str | None = typer.Option(None, help="Natural-language ICP prompt used to derive contact filters."),
    seniority: list[str] | None = typer.Option(None, help="Filter by seniority level (repeatable)."),
    negate_seniority: list[str] | None = typer.Option(None, help="Exclude seniority levels (repeatable)."),
    department: list[str] | None = typer.Option(None, help="Filter by department (repeatable)."),
    negate_department: list[str] | None = typer.Option(None, help="Exclude departments (repeatable)."),
    title: list[str] | None = typer.Option(None, help="Filter by job title (repeatable)."),
    negate_title: list[str] | None = typer.Option(None, help="Exclude job titles (repeatable)."),
    domain: list[str] | None = typer.Option(None, help="Filter by company domain (repeatable)."),
    person_country: list[str] | None = typer.Option(None, help="Filter by contact country (repeatable)."),
    negate_person_country: list[str] | None = typer.Option(None, help="Exclude contact countries (repeatable)."),
    filter_industry: list[str] | None = typer.Option(None, help="Filter by company industry (repeatable)."),
    negate_filter_industry: list[str] | None = typer.Option(None, help="Exclude company industries (repeatable)."),
    filter_country: list[str] | None = typer.Option(None, help="Filter by company country (repeatable)."),
    negate_filter_country: list[str] | None = typer.Option(None, help="Exclude company countries (repeatable)."),
    employee_range: str | None = typer.Option(None, help="Company employee range, e.g. 50-200."),
    has_email: bool | None = typer.Option(
        None, "--has-email/--no-has-email", help="Only contacts with (or without) an email address."
    ),
    jobstart_date: str | None = typer.Option(None, "--jobstart-date", help=JOBSTART_DATE_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
    param: list[str] | None = typer.Option(None, "--param", help=PARAM_HELP),
) -> None:
    """Count contacts matching the given filters."""
    from discolike_cli.main import get_client

    kwargs = _merge_params(
        param,
        icp_prompt=icp_prompt,
        seniority=seniority,
        negate_seniority=negate_seniority,
        department=department,
        negate_department=negate_department,
        title=title,
        negate_title=negate_title,
        domain=domain,
        person_country=person_country,
        negate_person_country=negate_person_country,
        filter_industry=filter_industry,
        negate_filter_industry=negate_filter_industry,
        filter_country=filter_country,
        negate_filter_country=negate_filter_country,
        employee_range=employee_range,
        has_email=has_email,
        jobstart_date=jobstart_date,
    )
    emit(call_typed(get_client(ctx).contacts.count, **kwargs), fmt=fmt)


@app.command("lookup")
@handle_errors
def lookup_command(
    ctx: typer.Context,
    persona_id: int | None = typer.Option(None, "--persona-id", help="Look up by persona ID."),
    linkedin: str | None = typer.Option(None, "--linkedin", help="Look up by LinkedIn profile URL."),
    email: str | None = typer.Option(None, "--email", help="Look up by email address."),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Look up a single contact by persona ID, LinkedIn URL, or email."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).contacts.lookup(persona_id=persona_id, linkedin=linkedin, email=email), fmt=fmt)


@app.command("match")
@handle_errors
def match_command(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Full name of the person to match."),
    company_name: str | None = typer.Option(None, "--company-name", help="Company name to narrow the match."),
    domain: str | None = typer.Option(None, "--domain", help="Company domain to narrow the match."),
    person_country: str | None = typer.Option(None, "--person-country", help="Contact country to narrow the match."),
    limit: int | None = typer.Option(None, "--limit", help="Maximum number of matches to return."),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Match a person name to contact records."""
    from discolike_cli.main import get_client

    emit(
        get_client(ctx).contacts.match(
            name=name,
            company_name=company_name,
            domain=domain,
            person_country=person_country,
            limit=limit,
        ),
        fmt=fmt,
    )


@app.command("bulk-match")
@handle_errors
def bulk_match_command(
    ctx: typer.Context,
    queries_file: pathlib.Path = typer.Option(
        ..., "--queries-file", help="Path to a JSON file with an array of match query objects."
    ),
    enrich: bool | None = typer.Option(
        None, "--enrich/--no-enrich", help="Enable or disable enrichment of matched contacts."
    ),
    limit: int | None = typer.Option(None, "--limit", help="Maximum number of matches per query."),
    wait: bool = typer.Option(False, "--wait", help=WAIT_HELP),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout", help=TIMEOUT_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Match many person queries in one async job."""
    from discolike_cli.main import get_client

    try:
        queries = json.loads(queries_file.read_text())
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"--queries-file must contain valid JSON: {exc}") from exc
    if not isinstance(queries, list):
        raise typer.BadParameter("--queries-file must contain a JSON array of objects")

    job = get_client(ctx).contacts.bulk_match(queries=queries, enrich=enrich, limit=limit)
    run_job(job, wait=wait, timeout=timeout, fmt=fmt)


@app.command("discover")
@handle_errors
def discover_command(
    ctx: typer.Context,
    icp_prompt: str | None = typer.Option(None, help="Natural-language ICP prompt used to derive contact filters."),
    seniority: list[str] | None = typer.Option(None, help="Filter by seniority level (repeatable)."),
    negate_seniority: list[str] | None = typer.Option(None, help="Exclude seniority levels (repeatable)."),
    department: list[str] | None = typer.Option(None, help="Filter by department (repeatable)."),
    negate_department: list[str] | None = typer.Option(None, help="Exclude departments (repeatable)."),
    title: list[str] | None = typer.Option(None, help="Filter by job title (repeatable)."),
    negate_title: list[str] | None = typer.Option(None, help="Exclude job titles (repeatable)."),
    domain: list[str] | None = typer.Option(None, help="Filter by company domain (repeatable)."),
    person_country: list[str] | None = typer.Option(None, help="Filter by contact country (repeatable)."),
    negate_person_country: list[str] | None = typer.Option(None, help="Exclude contact countries (repeatable)."),
    filter_industry: list[str] | None = typer.Option(None, help="Filter by company industry (repeatable)."),
    negate_filter_industry: list[str] | None = typer.Option(None, help="Exclude company industries (repeatable)."),
    filter_country: list[str] | None = typer.Option(None, help="Filter by company country (repeatable)."),
    negate_filter_country: list[str] | None = typer.Option(None, help="Exclude company countries (repeatable)."),
    employee_range: str | None = typer.Option(None, help="Company employee range, e.g. 50-200."),
    has_email: bool | None = typer.Option(
        None, "--has-email/--no-has-email", help="Only contacts with (or without) an email address."
    ),
    jobstart_date: str | None = typer.Option(None, "--jobstart-date", help=JOBSTART_DATE_HELP),
    max_records: int | None = typer.Option(None, help="Maximum number of contacts to return."),
    offset: int | None = typer.Option(None, help="Number of records to skip for pagination."),
    results_by_company: int | None = typer.Option(
        None, "--results-by-company", help="Maximum contacts returned per company."
    ),
    include_search_contacts: bool | None = typer.Option(
        None,
        "--include-search-contacts/--no-include-search-contacts",
        help="Include or exclude contacts from contact search in the results.",
    ),
    consensus: int | None = typer.Option(None, "--consensus", help="Consensus threshold for discovered contacts."),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
    param: list[str] | None = typer.Option(None, "--param", help=PARAM_HELP),
) -> None:
    """Discover contacts grouped by company for the given filters."""
    from discolike_cli.main import get_client

    kwargs = _merge_params(
        param,
        icp_prompt=icp_prompt,
        seniority=seniority,
        negate_seniority=negate_seniority,
        department=department,
        negate_department=negate_department,
        title=title,
        negate_title=negate_title,
        domain=domain,
        person_country=person_country,
        negate_person_country=negate_person_country,
        filter_industry=filter_industry,
        negate_filter_industry=negate_filter_industry,
        filter_country=filter_country,
        negate_filter_country=negate_filter_country,
        employee_range=employee_range,
        has_email=has_email,
        jobstart_date=jobstart_date,
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
    icp_text: str = typer.Option(..., "--icp-text", help="ICP description used to generate contacts."),
    domain: list[str] = typer.Option(..., "--domain", help="Target company domain (repeatable)."),
    context_mode: str | None = typer.Option(None, "--context-mode", help="Context mode for generation."),
    integration_id: str | None = typer.Option(None, "--integration-id", help="Integration ID to use for generation."),
    search_provider_id: str | None = typer.Option(
        None, "--search-provider-id", help="Search provider ID to use for generation."
    ),
    search_context_size: str | None = typer.Option(
        None, "--search-context-size", help="Search context size for the search provider."
    ),
    max_contacts_per_domain: int | None = typer.Option(
        None, "--max-contacts-per-domain", help="Maximum contacts generated per domain."
    ),
    max_company_records: int | None = typer.Option(
        None, "--max-company-records", help="Maximum company records to process."
    ),
    wait: bool = typer.Option(False, "--wait", help=WAIT_HELP),
    timeout: float = typer.Option(DEFAULT_WAIT_TIMEOUT_SECONDS, "--timeout", help=TIMEOUT_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Generate contacts for target domains from an ICP description (async job)."""
    from discolike_cli.main import get_client

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
    run_job(job, wait=wait, timeout=timeout, fmt=fmt)
