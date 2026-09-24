from __future__ import annotations

import pathlib
from typing import Any

import typer

from discolike.requests import CountParams
from discolike.requests import DiscoverParams
from discolike_cli._inputs import merge_domains
from discolike_cli._inputs import read_params_file
from discolike_cli._output import build_request
from discolike_cli._output import emit
from discolike_cli._output import handle_errors

PARAM_SEPARATOR = "="
LIST_VALUE_SEPARATOR = ","

FORMAT_HELP = "Output format: json or table (table auto-selected on a TTY; falls back to JSON for non-tabular data)."
PARAM_HELP = "Extra API parameter as KEY=VALUE (comma-separates into a list); see docs.discolike.com"
BBOX_HELP = "Bounding box as min_lat,min_lon,max_lat,max_lon (repeatable). Longitudes may wrap the antimeridian."
GEO_HELP = "Circular area as lat,lon or lat,lon,radius, e.g. 30.27,-97.74,30mi (repeatable). Radius defaults to 50km."
SHAPES_ARE_ORED_HELP = (
    "Every --geo circle, every --bbox and the --lat/--lon/--radius centre are OR'd together, up to 10 in total."
)
PARAMS_FILE_HELP = (
    "JSON object of API parameter names (e.g. an app form copied over); --param and flags override its values."
)
DOMAINS_FILE_HELP = "CSV with a 'domain' column, or one domain per line; merged with --domain."
EXCLUDE_DOMAINS_FILE_HELP = (
    "CSV with a 'domain' column, or one domain per line; merged with --exclude-domain (100 max)."
)
SUBDOMAIN_HELP = "Limit results to this subdomain, up to 20, each at least 3 characters (repeatable)."
NEGATE_SUBDOMAIN_HELP = "Exclude this subdomain, up to 20, each at least 3 characters (repeatable)."
START_DATE_HELP = "Minimum company start date (YYYY-MM-DD) or range (YYYY-MM-DD,YYYY-MM-DD)."
REDIRECT_HELP = "Include or exclude domains that redirect to another domain."
SOCIAL_HELP = (
    "Filter by social platform presence (repeatable): facebook, instagram, linkedin, pinterest, threads, tiktok, "
    "twitter, x, yelp, youtube, googleplay, applestore, amazon, vk, bluesky, xing."
)
NEGATE_SOCIAL_HELP = "Exclude companies with this social profile (repeatable); same values as --social."
LANGUAGE_HELP = "Filter by site language as an ISO 639-1 code, e.g. en, de, pb, zt (repeatable)."
NEGATE_LANGUAGE_HELP = "Exclude this site language (repeatable); same values as --language."
EXCLUDE_LEADGEN_HELP = "Exclude suspected lead generation sites (on by default)."
COUNT_EXCLUDE_LEADGEN_HELP = "Exclude suspected lead generation sites (off by default for count)."


def _parse_param(raw: str) -> tuple[str, str | list[str]]:
    if PARAM_SEPARATOR not in raw:
        raise typer.BadParameter(f"--param must be in KEY=VALUE form, got {raw!r}")
    key, _, value = raw.partition(PARAM_SEPARATOR)
    if LIST_VALUE_SEPARATOR in value:
        return key, value.split(LIST_VALUE_SEPARATOR)
    return key, value


def _merge_params(
    param: list[str] | None,
    params_file: pathlib.Path | None = None,
    **options: Any,  # noqa: ANN401 -- forwarded as a dict to build_request
) -> dict[str, Any]:
    """Precedence, lowest to highest: --params-file, --param KEY=VALUE, first-class flags."""
    kwargs: dict[str, Any] = read_params_file(params_file) if params_file is not None else {}
    kwargs.update(_parse_param(raw) for raw in param or [])
    kwargs.update({key: value for key, value in options.items() if value is not None})
    return kwargs


@handle_errors
def discover_command(
    ctx: typer.Context,
    icp_prompt: str | None = typer.Option(None, help="Natural-language ideal customer profile description."),
    domain: list[str] | None = typer.Option(None, help="Seed domain for lookalike matching (repeatable)."),
    phrase_match: list[str] | None = typer.Option(None, help="Phrase the company website must contain (repeatable)."),
    negate_phrase_match: list[str] | None = typer.Option(None, help="Negate the --phrase-match filter (repeatable)."),
    category: list[str] | None = typer.Option(None, help="Industry category filter (repeatable)."),
    negate_category: list[str] | None = typer.Option(None, help="Negate the --category filter (repeatable)."),
    sub_industry: list[str] | None = typer.Option(None, help="Sub-industry filter, bare or PARENT/SUB (repeatable)."),
    negate_sub_industry: list[str] | None = typer.Option(None, help="Negate the --sub-industry filter (repeatable)."),
    lat: float | None = typer.Option(None, help="Latitude of the search centre; requires --lon."),
    lon: float | None = typer.Option(None, help="Longitude of the search centre; requires --lat."),
    radius: str | None = typer.Option(None, help="Radius around --lat/--lon, e.g. 50km or 30mi. Default 50km."),
    geo: list[str] | None = typer.Option(None, help=f"{GEO_HELP} {SHAPES_ARE_ORED_HELP}"),
    bbox: list[str] | None = typer.Option(None, help=f"{BBOX_HELP} {SHAPES_ARE_ORED_HELP}"),
    country: list[str] | None = typer.Option(None, help="ISO country code filter (repeatable)."),
    negate_country: list[str] | None = typer.Option(None, help="Negate the --country filter (repeatable)."),
    state: list[str] | None = typer.Option(None, help="State or region filter (repeatable)."),
    negate_state: list[str] | None = typer.Option(None, help="Negate the --state filter (repeatable)."),
    subdomain: list[str] | None = typer.Option(None, help=SUBDOMAIN_HELP),
    negate_subdomain: list[str] | None = typer.Option(None, help=NEGATE_SUBDOMAIN_HELP),
    language: list[str] | None = typer.Option(None, help=LANGUAGE_HELP),
    negate_language: list[str] | None = typer.Option(None, help=NEGATE_LANGUAGE_HELP),
    social: list[str] | None = typer.Option(None, help=SOCIAL_HELP),
    negate_social: list[str] | None = typer.Option(None, help=NEGATE_SOCIAL_HELP),
    employee_range: str | None = typer.Option(None, help="Employee count range filter."),
    revenue_range: str | None = typer.Option(None, help="Revenue range filter."),
    start_date: str | None = typer.Option(None, help=START_DATE_HELP),
    business_model: list[str] | None = typer.Option(None, help="Business model filter (repeatable)."),
    negate_business_model: list[str] | None = typer.Option(
        None, help="Negate the --business-model filter (repeatable)."
    ),
    tech_stack: list[str] | None = typer.Option(None, help="Technology stack filter (repeatable)."),
    negate_tech_stack: list[str] | None = typer.Option(None, help="Negate the --tech-stack filter (repeatable)."),
    min_digital_footprint: int | None = typer.Option(None, help="Minimum digital footprint score."),
    max_digital_footprint: int | None = typer.Option(None, help="Maximum digital footprint score."),
    min_similarity: int | None = typer.Option(None, help="Minimum similarity score to include (0-99)."),
    variance: str | None = typer.Option(
        None, help="Result diversity control: LOW, MID_LOW, MEDIUM, MID_HIGH, HIGH, UNRESTRICTED."
    ),
    consensus: int | None = typer.Option(
        None, help="Number of top results for the consensus search vector (1-20); higher reduces specificity."
    ),
    redirect: bool | None = typer.Option(None, "--redirect/--no-redirect", help=REDIRECT_HELP),
    exclude_leadgen: bool | None = typer.Option(
        None, "--exclude-leadgen/--no-exclude-leadgen", help=EXCLUDE_LEADGEN_HELP
    ),
    retrieval: bool | None = typer.Option(
        None, "--retrieval/--no-retrieval", help="Enable page data retrieval using the Extract API."
    ),
    enhanced: bool | None = typer.Option(
        None, "--enhanced/--no-enhanced", help="Enable AI-powered result enhancement for improved relevance."
    ),
    include_search_domains: bool | None = typer.Option(
        None,
        "--include-search-domains/--no-include-search-domains",
        help="Include the input domains in results (excluded by default).",
    ),
    auto_icp_text: bool | None = typer.Option(
        None, "--auto-icp-text/--no-auto-icp-text", help="Auto-generate ICP text from the provided domain(s)."
    ),
    auto_phrase_match: bool | None = typer.Option(
        None, "--auto-phrase-match/--no-auto-phrase-match", help="Auto-generate phrase matches from ICP text."
    ),
    exclude_domain: list[str] | None = typer.Option(None, help="Domain to exclude from results (repeatable)."),
    exclude_domains_file: pathlib.Path | None = typer.Option(None, help=EXCLUDE_DOMAINS_FILE_HELP),
    inclusion_query_id: list[str] | None = typer.Option(
        None, help="Saved query ID whose domains are included (repeatable); requires the STARTER plan."
    ),
    exclusion_query_id: list[str] | None = typer.Option(
        None, help="Saved query ID whose results are excluded (repeatable)."
    ),
    max_records: int | None = typer.Option(None, help="Maximum number of companies to return."),
    offset: int | None = typer.Option(None, help="Number of records to skip for pagination."),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
    param: list[str] | None = typer.Option(None, "--param", help=PARAM_HELP),
    params_file: pathlib.Path | None = typer.Option(None, help=PARAMS_FILE_HELP),
) -> None:
    """Discover companies matching your ICP and filters."""
    from discolike_cli.main import get_client

    request = build_request(
        DiscoverParams,
        _merge_params(
            param,
            params_file,
            icp_prompt=icp_prompt,
            domain=domain,
            phrase_match=phrase_match,
            negate_phrase_match=negate_phrase_match,
            category=category,
            negate_category=negate_category,
            sub_industry=sub_industry,
            negate_sub_industry=negate_sub_industry,
            lat=lat,
            lon=lon,
            radius=radius,
            geo=geo,
            bbox=bbox,
            country=country,
            negate_country=negate_country,
            state=state,
            negate_state=negate_state,
            subdomain=subdomain,
            negate_subdomain=negate_subdomain,
            language=language,
            negate_language=negate_language,
            social=social,
            negate_social=negate_social,
            employee_range=employee_range,
            revenue_range=revenue_range,
            start_date=start_date,
            business_model=business_model,
            negate_business_model=negate_business_model,
            tech_stack=tech_stack,
            negate_tech_stack=negate_tech_stack,
            min_digital_footprint=min_digital_footprint,
            max_digital_footprint=max_digital_footprint,
            min_similarity=min_similarity,
            variance=variance,
            consensus=consensus,
            redirect=redirect,
            exclude_leadgen=exclude_leadgen,
            retrieval=retrieval,
            enhanced=enhanced,
            include_search_domains=include_search_domains,
            auto_icp_text=auto_icp_text,
            auto_phrase_match=auto_phrase_match,
            exclude_domain=merge_domains(exclude_domain, exclude_domains_file),
            inclusion_query_id=inclusion_query_id,
            exclusion_query_id=exclusion_query_id,
            max_records=max_records,
            offset=offset,
        ),
    )
    emit(get_client(ctx).discover(request), fmt=fmt)


@handle_errors
def count_command(
    ctx: typer.Context,
    phrase_match: list[str] | None = typer.Option(None, help="Phrase the company website must contain (repeatable)."),
    negate_phrase_match: list[str] | None = typer.Option(None, help="Negate the --phrase-match filter (repeatable)."),
    category: list[str] | None = typer.Option(None, help="Industry category filter (repeatable)."),
    negate_category: list[str] | None = typer.Option(None, help="Negate the --category filter (repeatable)."),
    sub_industry: list[str] | None = typer.Option(None, help="Sub-industry filter, bare or PARENT/SUB (repeatable)."),
    negate_sub_industry: list[str] | None = typer.Option(None, help="Negate the --sub-industry filter (repeatable)."),
    lat: float | None = typer.Option(None, help="Latitude of the search centre; requires --lon."),
    lon: float | None = typer.Option(None, help="Longitude of the search centre; requires --lat."),
    radius: str | None = typer.Option(None, help="Radius around --lat/--lon, e.g. 50km or 30mi. Default 50km."),
    geo: list[str] | None = typer.Option(None, help=f"{GEO_HELP} {SHAPES_ARE_ORED_HELP}"),
    bbox: list[str] | None = typer.Option(None, help=f"{BBOX_HELP} {SHAPES_ARE_ORED_HELP}"),
    country: list[str] | None = typer.Option(None, help="ISO country code filter (repeatable)."),
    negate_country: list[str] | None = typer.Option(None, help="Negate the --country filter (repeatable)."),
    state: list[str] | None = typer.Option(None, help="State or region filter (repeatable)."),
    negate_state: list[str] | None = typer.Option(None, help="Negate the --state filter (repeatable)."),
    subdomain: list[str] | None = typer.Option(None, help=SUBDOMAIN_HELP),
    negate_subdomain: list[str] | None = typer.Option(None, help=NEGATE_SUBDOMAIN_HELP),
    language: list[str] | None = typer.Option(None, help=LANGUAGE_HELP),
    negate_language: list[str] | None = typer.Option(None, help=NEGATE_LANGUAGE_HELP),
    social: list[str] | None = typer.Option(None, help=SOCIAL_HELP),
    negate_social: list[str] | None = typer.Option(None, help=NEGATE_SOCIAL_HELP),
    employee_range: str | None = typer.Option(None, help="Employee count range filter."),
    revenue_range: str | None = typer.Option(None, help="Revenue range filter."),
    start_date: str | None = typer.Option(None, help=START_DATE_HELP),
    business_model: list[str] | None = typer.Option(None, help="Business model filter (repeatable)."),
    negate_business_model: list[str] | None = typer.Option(
        None, help="Negate the --business-model filter (repeatable)."
    ),
    tech_stack: list[str] | None = typer.Option(None, help="Technology stack filter (repeatable)."),
    negate_tech_stack: list[str] | None = typer.Option(None, help="Negate the --tech-stack filter (repeatable)."),
    min_digital_footprint: int | None = typer.Option(None, help="Minimum digital footprint score."),
    max_digital_footprint: int | None = typer.Option(None, help="Maximum digital footprint score."),
    redirect: bool | None = typer.Option(None, "--redirect/--no-redirect", help=REDIRECT_HELP),
    exclude_leadgen: bool | None = typer.Option(
        None, "--exclude-leadgen/--no-exclude-leadgen", help=COUNT_EXCLUDE_LEADGEN_HELP
    ),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
    param: list[str] | None = typer.Option(None, "--param", help=PARAM_HELP),
    params_file: pathlib.Path | None = typer.Option(None, help=PARAMS_FILE_HELP),
) -> None:
    """Count companies matching the given filters."""
    from discolike_cli.main import get_client

    request = build_request(
        CountParams,
        _merge_params(
            param,
            params_file,
            phrase_match=phrase_match,
            negate_phrase_match=negate_phrase_match,
            category=category,
            negate_category=negate_category,
            sub_industry=sub_industry,
            negate_sub_industry=negate_sub_industry,
            lat=lat,
            lon=lon,
            radius=radius,
            geo=geo,
            bbox=bbox,
            country=country,
            negate_country=negate_country,
            state=state,
            negate_state=negate_state,
            subdomain=subdomain,
            negate_subdomain=negate_subdomain,
            language=language,
            negate_language=negate_language,
            social=social,
            negate_social=negate_social,
            employee_range=employee_range,
            revenue_range=revenue_range,
            start_date=start_date,
            business_model=business_model,
            negate_business_model=negate_business_model,
            tech_stack=tech_stack,
            negate_tech_stack=negate_tech_stack,
            min_digital_footprint=min_digital_footprint,
            max_digital_footprint=max_digital_footprint,
            redirect=redirect,
            exclude_leadgen=exclude_leadgen,
        ),
    )
    emit(get_client(ctx).count(request), fmt=fmt)
