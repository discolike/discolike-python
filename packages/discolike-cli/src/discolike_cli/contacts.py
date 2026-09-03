from __future__ import annotations

import json
import pathlib

import typer

from discolike.requests import BulkContactMatchRequest
from discolike.requests import ContactFilters
from discolike.requests import ContactGenerateRequest
from discolike.requests import ContactsCountParams
from discolike.requests import ContactsLookupParams
from discolike.requests import ContactsMatchParams
from discolike.requests import ContactsSearchParams
from discolike_cli._output import build_request
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
SUMMARY_HELP = "Filter by profile summary text (semantic search)."
NEGATE_SUMMARY_HELP = "Exclude contacts matching this summary description."
NAME_HELP = "Filter by contact name (partial match supported)."
SKILLS_HELP = "Filter by skill (repeatable)."
FILTER_STATE_HELP = "Filter by company state/region (repeatable)."
NEGATE_FILTER_STATE_HELP = "Exclude contacts at companies in this state (repeatable)."
PERSON_STATE_HELP = "Filter by contact state/region (repeatable)."
PERSONA_ID_HELP = "Filter by persona ID (repeatable)."
EMAIL_VALIDATED_HELP = "Only contacts with (or without) a validated email address."
HAS_PHONE_HELP = "Only contacts with (or without) a phone number."
HAS_MOBILE_HELP = "Only contacts with (or without) a mobile phone number."
HAS_LINKEDIN_HELP = "Only contacts with (or without) a LinkedIn profile."
MIN_CONNECTIONS_HELP = "Minimum LinkedIn connections required."
INCLUSION_QUERY_ID_HELP = "Include only contacts from companies in this saved query (repeatable)."
EXCLUSION_QUERY_ID_HELP = "Exclude contacts from companies in this saved query (repeatable)."
MAX_COMPANIES_HELP = "Maximum number of enriched companies to return; cannot be combined with --max-records."
RESULTS_BY_COMPANY_HELP = "Maximum contacts per company domain (default 5; 0 removes the cap)."
INCLUDE_SEARCH_CONTACTS_HELP = "Include contacts from the search index (broader coverage)."
CONSENSUS_HELP = "Number of query vectors to combine for consensus search."

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
    name: str | None = typer.Option(None, help=NAME_HELP),
    summary: str | None = typer.Option(None, help=SUMMARY_HELP),
    negate_summary: str | None = typer.Option(None, help=NEGATE_SUMMARY_HELP),
    skills: list[str] | None = typer.Option(None, help=SKILLS_HELP),
    domain: list[str] | None = typer.Option(None, help="Filter by company domain (repeatable)."),
    person_country: list[str] | None = typer.Option(None, help="Filter by contact country (repeatable)."),
    negate_person_country: list[str] | None = typer.Option(None, help="Exclude contact countries (repeatable)."),
    person_state: list[str] | None = typer.Option(None, help=PERSON_STATE_HELP),
    persona_id: list[int] | None = typer.Option(None, help=PERSONA_ID_HELP),
    filter_industry: list[str] | None = typer.Option(None, help="Filter by company industry (repeatable)."),
    negate_filter_industry: list[str] | None = typer.Option(None, help="Exclude company industries (repeatable)."),
    filter_country: list[str] | None = typer.Option(None, help="Filter by company country (repeatable)."),
    negate_filter_country: list[str] | None = typer.Option(None, help="Exclude company countries (repeatable)."),
    filter_state: list[str] | None = typer.Option(None, help=FILTER_STATE_HELP),
    negate_filter_state: list[str] | None = typer.Option(None, help=NEGATE_FILTER_STATE_HELP),
    employee_range: str | None = typer.Option(None, help="Company employee range, e.g. 50-200."),
    has_email: bool | None = typer.Option(
        None, "--has-email/--no-has-email", help="Only contacts with (or without) an email address."
    ),
    email_validated: bool | None = typer.Option(
        None, "--email-validated/--no-email-validated", help=EMAIL_VALIDATED_HELP
    ),
    has_phone: bool | None = typer.Option(None, "--has-phone/--no-has-phone", help=HAS_PHONE_HELP),
    has_mobile: bool | None = typer.Option(None, "--has-mobile/--no-has-mobile", help=HAS_MOBILE_HELP),
    has_linkedin: bool | None = typer.Option(None, "--has-linkedin/--no-has-linkedin", help=HAS_LINKEDIN_HELP),
    min_connections: int | None = typer.Option(None, help=MIN_CONNECTIONS_HELP),
    jobstart_date: str | None = typer.Option(None, "--jobstart-date", help=JOBSTART_DATE_HELP),
    inclusion_query_id: list[str] | None = typer.Option(None, help=INCLUSION_QUERY_ID_HELP),
    exclusion_query_id: list[str] | None = typer.Option(None, help=EXCLUSION_QUERY_ID_HELP),
    max_records: int | None = typer.Option(None, help="Maximum number of contacts to return."),
    max_companies: int | None = typer.Option(None, help=MAX_COMPANIES_HELP),
    offset: int | None = typer.Option(None, help="Number of records to skip for pagination."),
    results_by_company: int | None = typer.Option(None, help=RESULTS_BY_COMPANY_HELP),
    include_search_contacts: bool | None = typer.Option(
        None, "--include-search-contacts/--no-include-search-contacts", help=INCLUDE_SEARCH_CONTACTS_HELP
    ),
    consensus: int | None = typer.Option(None, help=CONSENSUS_HELP),
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
        name=name,
        summary=summary,
        negate_summary=negate_summary,
        skills=skills,
        domain=domain,
        person_country=person_country,
        negate_person_country=negate_person_country,
        person_state=person_state,
        persona_id=persona_id,
        filter_industry=filter_industry,
        negate_filter_industry=negate_filter_industry,
        filter_country=filter_country,
        negate_filter_country=negate_filter_country,
        filter_state=filter_state,
        negate_filter_state=negate_filter_state,
        employee_range=employee_range,
        has_email=has_email,
        email_validated=email_validated,
        has_phone=has_phone,
        has_mobile=has_mobile,
        has_linkedin=has_linkedin,
        min_connections=min_connections,
        jobstart_date=jobstart_date,
        inclusion_query_id=inclusion_query_id,
        exclusion_query_id=exclusion_query_id,
        max_records=max_records,
        max_companies=max_companies,
        offset=offset,
        results_by_company=results_by_company,
        include_search_contacts=include_search_contacts,
        consensus=consensus,
    )
    emit(get_client(ctx).contacts.search(build_request(ContactsSearchParams, kwargs)), fmt=fmt)


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
    name: str | None = typer.Option(None, help=NAME_HELP),
    summary: str | None = typer.Option(None, help=SUMMARY_HELP),
    negate_summary: str | None = typer.Option(None, help=NEGATE_SUMMARY_HELP),
    skills: list[str] | None = typer.Option(None, help=SKILLS_HELP),
    domain: list[str] | None = typer.Option(None, help="Filter by company domain (repeatable)."),
    person_country: list[str] | None = typer.Option(None, help="Filter by contact country (repeatable)."),
    negate_person_country: list[str] | None = typer.Option(None, help="Exclude contact countries (repeatable)."),
    person_state: list[str] | None = typer.Option(None, help=PERSON_STATE_HELP),
    persona_id: list[int] | None = typer.Option(None, help=PERSONA_ID_HELP),
    filter_industry: list[str] | None = typer.Option(None, help="Filter by company industry (repeatable)."),
    negate_filter_industry: list[str] | None = typer.Option(None, help="Exclude company industries (repeatable)."),
    filter_country: list[str] | None = typer.Option(None, help="Filter by company country (repeatable)."),
    negate_filter_country: list[str] | None = typer.Option(None, help="Exclude company countries (repeatable)."),
    filter_state: list[str] | None = typer.Option(None, help=FILTER_STATE_HELP),
    negate_filter_state: list[str] | None = typer.Option(None, help=NEGATE_FILTER_STATE_HELP),
    employee_range: str | None = typer.Option(None, help="Company employee range, e.g. 50-200."),
    has_email: bool | None = typer.Option(
        None, "--has-email/--no-has-email", help="Only contacts with (or without) an email address."
    ),
    email_validated: bool | None = typer.Option(
        None, "--email-validated/--no-email-validated", help=EMAIL_VALIDATED_HELP
    ),
    has_phone: bool | None = typer.Option(None, "--has-phone/--no-has-phone", help=HAS_PHONE_HELP),
    has_mobile: bool | None = typer.Option(None, "--has-mobile/--no-has-mobile", help=HAS_MOBILE_HELP),
    has_linkedin: bool | None = typer.Option(None, "--has-linkedin/--no-has-linkedin", help=HAS_LINKEDIN_HELP),
    min_connections: int | None = typer.Option(None, help=MIN_CONNECTIONS_HELP),
    jobstart_date: str | None = typer.Option(None, "--jobstart-date", help=JOBSTART_DATE_HELP),
    inclusion_query_id: list[str] | None = typer.Option(None, help=INCLUSION_QUERY_ID_HELP),
    exclusion_query_id: list[str] | None = typer.Option(None, help=EXCLUSION_QUERY_ID_HELP),
    max_records: int | None = typer.Option(None, help="Maximum number of contacts to count (20-10000)."),
    max_companies: int | None = typer.Option(None, help=MAX_COMPANIES_HELP),
    offset: int | None = typer.Option(None, help="Number of records to skip for pagination."),
    results_by_company: int | None = typer.Option(None, help=RESULTS_BY_COMPANY_HELP),
    include_search_contacts: bool | None = typer.Option(
        None, "--include-search-contacts/--no-include-search-contacts", help=INCLUDE_SEARCH_CONTACTS_HELP
    ),
    consensus: int | None = typer.Option(None, help=CONSENSUS_HELP),
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
        name=name,
        summary=summary,
        negate_summary=negate_summary,
        skills=skills,
        domain=domain,
        person_country=person_country,
        negate_person_country=negate_person_country,
        person_state=person_state,
        persona_id=persona_id,
        filter_industry=filter_industry,
        negate_filter_industry=negate_filter_industry,
        filter_country=filter_country,
        negate_filter_country=negate_filter_country,
        filter_state=filter_state,
        negate_filter_state=negate_filter_state,
        employee_range=employee_range,
        has_email=has_email,
        email_validated=email_validated,
        has_phone=has_phone,
        has_mobile=has_mobile,
        has_linkedin=has_linkedin,
        min_connections=min_connections,
        jobstart_date=jobstart_date,
        inclusion_query_id=inclusion_query_id,
        exclusion_query_id=exclusion_query_id,
        max_records=max_records,
        max_companies=max_companies,
        offset=offset,
        results_by_company=results_by_company,
        include_search_contacts=include_search_contacts,
        consensus=consensus,
    )
    emit(get_client(ctx).contacts.count(build_request(ContactsCountParams, kwargs)), fmt=fmt)


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

    request = build_request(
        ContactsLookupParams, _merge_params(None, persona_id=persona_id, linkedin=linkedin, email=email)
    )
    emit(get_client(ctx).contacts.lookup(request), fmt=fmt)


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

    request = build_request(
        ContactsMatchParams,
        _merge_params(
            None, name=name, company_name=company_name, domain=domain, person_country=person_country, limit=limit
        ),
    )
    emit(get_client(ctx).contacts.match(request), fmt=fmt)


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

    request = build_request(BulkContactMatchRequest, _merge_params(None, queries=queries, enrich=enrich, limit=limit))
    run_job(get_client(ctx).contacts.bulk_match(request), wait=wait, timeout=timeout, fmt=fmt)


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
    name: str | None = typer.Option(None, help=NAME_HELP),
    summary: str | None = typer.Option(None, help=SUMMARY_HELP),
    negate_summary: str | None = typer.Option(None, help=NEGATE_SUMMARY_HELP),
    skills: list[str] | None = typer.Option(None, help=SKILLS_HELP),
    domain: list[str] | None = typer.Option(None, help="Filter by company domain (repeatable)."),
    person_country: list[str] | None = typer.Option(None, help="Filter by contact country (repeatable)."),
    negate_person_country: list[str] | None = typer.Option(None, help="Exclude contact countries (repeatable)."),
    person_state: list[str] | None = typer.Option(None, help=PERSON_STATE_HELP),
    persona_id: list[int] | None = typer.Option(None, help=PERSONA_ID_HELP),
    filter_industry: list[str] | None = typer.Option(None, help="Filter by company industry (repeatable)."),
    negate_filter_industry: list[str] | None = typer.Option(None, help="Exclude company industries (repeatable)."),
    filter_country: list[str] | None = typer.Option(None, help="Filter by company country (repeatable)."),
    negate_filter_country: list[str] | None = typer.Option(None, help="Exclude company countries (repeatable)."),
    filter_state: list[str] | None = typer.Option(None, help=FILTER_STATE_HELP),
    negate_filter_state: list[str] | None = typer.Option(None, help=NEGATE_FILTER_STATE_HELP),
    employee_range: str | None = typer.Option(None, help="Company employee range, e.g. 50-200."),
    has_email: bool | None = typer.Option(
        None, "--has-email/--no-has-email", help="Only contacts with (or without) an email address."
    ),
    email_validated: bool | None = typer.Option(
        None, "--email-validated/--no-email-validated", help=EMAIL_VALIDATED_HELP
    ),
    has_phone: bool | None = typer.Option(None, "--has-phone/--no-has-phone", help=HAS_PHONE_HELP),
    has_mobile: bool | None = typer.Option(None, "--has-mobile/--no-has-mobile", help=HAS_MOBILE_HELP),
    has_linkedin: bool | None = typer.Option(None, "--has-linkedin/--no-has-linkedin", help=HAS_LINKEDIN_HELP),
    min_connections: int | None = typer.Option(None, help=MIN_CONNECTIONS_HELP),
    jobstart_date: str | None = typer.Option(None, "--jobstart-date", help=JOBSTART_DATE_HELP),
    inclusion_query_id: list[str] | None = typer.Option(None, help=INCLUSION_QUERY_ID_HELP),
    exclusion_query_id: list[str] | None = typer.Option(None, help=EXCLUSION_QUERY_ID_HELP),
    max_records: int | None = typer.Option(None, help="Maximum number of contacts to return."),
    max_companies: int | None = typer.Option(None, help=MAX_COMPANIES_HELP),
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
        name=name,
        summary=summary,
        negate_summary=negate_summary,
        skills=skills,
        domain=domain,
        person_country=person_country,
        negate_person_country=negate_person_country,
        person_state=person_state,
        persona_id=persona_id,
        filter_industry=filter_industry,
        negate_filter_industry=negate_filter_industry,
        filter_country=filter_country,
        negate_filter_country=negate_filter_country,
        filter_state=filter_state,
        negate_filter_state=negate_filter_state,
        employee_range=employee_range,
        has_email=has_email,
        email_validated=email_validated,
        has_phone=has_phone,
        has_mobile=has_mobile,
        has_linkedin=has_linkedin,
        min_connections=min_connections,
        jobstart_date=jobstart_date,
        inclusion_query_id=inclusion_query_id,
        exclusion_query_id=exclusion_query_id,
        max_records=max_records,
        max_companies=max_companies,
        offset=offset,
        results_by_company=results_by_company,
        include_search_contacts=include_search_contacts,
        consensus=consensus,
    )
    emit(get_client(ctx).contacts.discover(build_request(ContactFilters, kwargs)), fmt=fmt)


@app.command("generate")
@handle_errors
def generate_command(
    ctx: typer.Context,
    icp_text: str = typer.Option(..., "--icp-text", help="ICP description used to generate contacts."),
    domain: list[str] = typer.Option(..., "--domain", help="Target company domain (repeatable)."),
    full_domain: list[str] | None = typer.Option(
        None, "--full-domain", help="Domain to send as full_domains to the generation job (repeatable)."
    ),
    partial_domain: list[str] | None = typer.Option(
        None, "--partial-domain", help="Domain to send as partial_domains to the generation job (repeatable)."
    ),
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

    request = build_request(
        ContactGenerateRequest,
        _merge_params(
            None,
            icp_text=icp_text,
            domains=domain,
            full_domains=full_domain,
            partial_domains=partial_domain,
            context_mode=context_mode,
            integration_id=integration_id,
            search_provider_id=search_provider_id,
            search_context_size=search_context_size,
            max_contacts_per_domain=max_contacts_per_domain,
            max_company_records=max_company_records,
        ),
    )
    run_job(get_client(ctx).contacts.generate(request), wait=wait, timeout=timeout, fmt=fmt)
