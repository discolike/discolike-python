from __future__ import annotations

from typing import Any

import typer

from discolike.cli._output import call_typed
from discolike.cli._output import emit
from discolike.cli._output import handle_errors

PARAM_SEPARATOR = "="
LIST_VALUE_SEPARATOR = ","


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
    icp_prompt: str | None = typer.Option(None),
    icp_text: str | None = typer.Option(None),
    domain: list[str] | None = typer.Option(None),
    phrase_match: list[str] | None = typer.Option(None),
    category: list[str] | None = typer.Option(None),
    country: list[str] | None = typer.Option(None),
    state: list[str] | None = typer.Option(None),
    employee_range: str | None = typer.Option(None),
    revenue_range: str | None = typer.Option(None),
    business_model: list[str] | None = typer.Option(None),
    tech_stack: list[str] | None = typer.Option(None),
    min_digital_footprint: int | None = typer.Option(None),
    max_digital_footprint: int | None = typer.Option(None),
    exclude_domain: list[str] | None = typer.Option(None),
    exclusion_query_id: list[str] | None = typer.Option(None),
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
        domain=domain,
        phrase_match=phrase_match,
        category=category,
        country=country,
        state=state,
        employee_range=employee_range,
        revenue_range=revenue_range,
        business_model=business_model,
        tech_stack=tech_stack,
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
    phrase_match: list[str] | None = typer.Option(None),
    category: list[str] | None = typer.Option(None),
    country: list[str] | None = typer.Option(None),
    state: list[str] | None = typer.Option(None),
    employee_range: str | None = typer.Option(None),
    revenue_range: str | None = typer.Option(None),
    business_model: list[str] | None = typer.Option(None),
    tech_stack: list[str] | None = typer.Option(None),
    min_digital_footprint: int | None = typer.Option(None),
    max_digital_footprint: int | None = typer.Option(None),
    fmt: str | None = typer.Option(None, "--format"),
    param: list[str] | None = typer.Option(None, "--param"),
) -> None:
    from discolike.cli.main import get_client

    kwargs = _merge_params(
        param,
        phrase_match=phrase_match,
        category=category,
        country=country,
        state=state,
        employee_range=employee_range,
        revenue_range=revenue_range,
        business_model=business_model,
        tech_stack=tech_stack,
        min_digital_footprint=min_digital_footprint,
        max_digital_footprint=max_digital_footprint,
    )
    count = call_typed(get_client(ctx).count, **kwargs)
    emit(count, fmt=fmt)
