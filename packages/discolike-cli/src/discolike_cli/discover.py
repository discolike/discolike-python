from __future__ import annotations

from typing import Any

import typer

from discolike_cli._output import call_typed
from discolike_cli._output import emit
from discolike_cli._output import handle_errors

PARAM_SEPARATOR = "="
LIST_VALUE_SEPARATOR = ","

FORMAT_HELP = "Output format: json or table (table auto-selected on a TTY; falls back to JSON for non-tabular data)."
PARAM_HELP = "Extra API parameter as KEY=VALUE (comma-separates into a list); see docs.discolike.com"


def _parse_param(raw: str) -> tuple[str, str | list[str]]:
    if PARAM_SEPARATOR not in raw:
        raise typer.BadParameter(f"--param must be in KEY=VALUE form, got {raw!r}")
    key, _, value = raw.partition(PARAM_SEPARATOR)
    if LIST_VALUE_SEPARATOR in value:
        return key, value.split(LIST_VALUE_SEPARATOR)
    return key, value


def _merge_params(param: list[str] | None, **options: Any) -> dict[str, Any]:  # noqa: ANN401 -- forwarded as **kwargs to typed resource/client methods
    kwargs: dict[str, Any] = dict(_parse_param(raw) for raw in param or [])
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
    country: list[str] | None = typer.Option(None, help="ISO country code filter (repeatable)."),
    negate_country: list[str] | None = typer.Option(None, help="Negate the --country filter (repeatable)."),
    state: list[str] | None = typer.Option(None, help="State or region filter (repeatable)."),
    negate_state: list[str] | None = typer.Option(None, help="Negate the --state filter (repeatable)."),
    employee_range: str | None = typer.Option(None, help="Employee count range filter."),
    revenue_range: str | None = typer.Option(None, help="Revenue range filter."),
    business_model: list[str] | None = typer.Option(None, help="Business model filter (repeatable)."),
    negate_business_model: list[str] | None = typer.Option(
        None, help="Negate the --business-model filter (repeatable)."
    ),
    tech_stack: list[str] | None = typer.Option(None, help="Technology stack filter (repeatable)."),
    negate_tech_stack: list[str] | None = typer.Option(None, help="Negate the --tech-stack filter (repeatable)."),
    min_digital_footprint: int | None = typer.Option(None, help="Minimum digital footprint score."),
    max_digital_footprint: int | None = typer.Option(None, help="Maximum digital footprint score."),
    exclude_domain: list[str] | None = typer.Option(None, help="Domain to exclude from results (repeatable)."),
    exclusion_query_id: list[str] | None = typer.Option(
        None, help="Saved query ID whose results are excluded (repeatable)."
    ),
    max_records: int | None = typer.Option(None, help="Maximum number of companies to return."),
    offset: int | None = typer.Option(None, help="Number of records to skip for pagination."),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
    param: list[str] | None = typer.Option(None, "--param", help=PARAM_HELP),
) -> None:
    """Discover companies matching your ICP and filters."""
    from discolike_cli.main import get_client

    kwargs = _merge_params(
        param,
        icp_prompt=icp_prompt,
        domain=domain,
        phrase_match=phrase_match,
        negate_phrase_match=negate_phrase_match,
        category=category,
        negate_category=negate_category,
        country=country,
        negate_country=negate_country,
        state=state,
        negate_state=negate_state,
        employee_range=employee_range,
        revenue_range=revenue_range,
        business_model=business_model,
        negate_business_model=negate_business_model,
        tech_stack=tech_stack,
        negate_tech_stack=negate_tech_stack,
        min_digital_footprint=min_digital_footprint,
        max_digital_footprint=max_digital_footprint,
        exclude_domain=exclude_domain,
        exclusion_query_id=exclusion_query_id,
        max_records=max_records,
        offset=offset,
    )
    companies = call_typed(get_client(ctx).discover, **kwargs)
    emit(companies, fmt=fmt)


@handle_errors
def count_command(
    ctx: typer.Context,
    phrase_match: list[str] | None = typer.Option(None, help="Phrase the company website must contain (repeatable)."),
    negate_phrase_match: list[str] | None = typer.Option(None, help="Negate the --phrase-match filter (repeatable)."),
    category: list[str] | None = typer.Option(None, help="Industry category filter (repeatable)."),
    negate_category: list[str] | None = typer.Option(None, help="Negate the --category filter (repeatable)."),
    country: list[str] | None = typer.Option(None, help="ISO country code filter (repeatable)."),
    negate_country: list[str] | None = typer.Option(None, help="Negate the --country filter (repeatable)."),
    state: list[str] | None = typer.Option(None, help="State or region filter (repeatable)."),
    negate_state: list[str] | None = typer.Option(None, help="Negate the --state filter (repeatable)."),
    employee_range: str | None = typer.Option(None, help="Employee count range filter."),
    revenue_range: str | None = typer.Option(None, help="Revenue range filter."),
    business_model: list[str] | None = typer.Option(None, help="Business model filter (repeatable)."),
    negate_business_model: list[str] | None = typer.Option(
        None, help="Negate the --business-model filter (repeatable)."
    ),
    tech_stack: list[str] | None = typer.Option(None, help="Technology stack filter (repeatable)."),
    negate_tech_stack: list[str] | None = typer.Option(None, help="Negate the --tech-stack filter (repeatable)."),
    min_digital_footprint: int | None = typer.Option(None, help="Minimum digital footprint score."),
    max_digital_footprint: int | None = typer.Option(None, help="Maximum digital footprint score."),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
    param: list[str] | None = typer.Option(None, "--param", help=PARAM_HELP),
) -> None:
    """Count companies matching the given filters."""
    from discolike_cli.main import get_client

    kwargs = _merge_params(
        param,
        phrase_match=phrase_match,
        negate_phrase_match=negate_phrase_match,
        category=category,
        negate_category=negate_category,
        country=country,
        negate_country=negate_country,
        state=state,
        negate_state=negate_state,
        employee_range=employee_range,
        revenue_range=revenue_range,
        business_model=business_model,
        negate_business_model=negate_business_model,
        tech_stack=tech_stack,
        negate_tech_stack=negate_tech_stack,
        min_digital_footprint=min_digital_footprint,
        max_digital_footprint=max_digital_footprint,
    )
    count = call_typed(get_client(ctx).count, **kwargs)
    emit(count, fmt=fmt)
