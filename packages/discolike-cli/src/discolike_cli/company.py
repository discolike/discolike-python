from __future__ import annotations

import typer

from discolike_cli._output import emit
from discolike_cli._output import handle_errors

FORMAT_HELP = "Output format: json or table (table auto-selected on a TTY; falls back to JSON for non-tabular data)."
DOMAIN_HELP = "Company domain, e.g. stripe.com"
MATCH_HELP = "Domain match mode, e.g. loose"

app = typer.Typer(
    help="Company profiles by domain: firmographics, scores, growth, redirects, vendors, subsidiaries, and public links."
)


@app.command()
@handle_errors
def data(
    ctx: typer.Context,
    domain: str = typer.Argument(..., help=DOMAIN_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Full company profile (firmographics) for a domain."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).companies.data(domain=domain), fmt=fmt)


@app.command()
@handle_errors
def score(
    ctx: typer.Context,
    domain: str = typer.Argument(..., help=DOMAIN_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Company score for a domain."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).companies.score(domain=domain), fmt=fmt)


@app.command()
@handle_errors
def growth(
    ctx: typer.Context,
    domain: str = typer.Argument(..., help=DOMAIN_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Growth signals for a domain."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).companies.growth(domain=domain), fmt=fmt)


@app.command()
@handle_errors
def redirects(
    ctx: typer.Context,
    domain: str = typer.Argument(..., help=DOMAIN_HELP),
    match: str | None = typer.Option(None, "--match", help=MATCH_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Domain redirects for a company domain."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).companies.redirects(domain=domain, match=match), fmt=fmt)


@app.command()
@handle_errors
def vendors(
    ctx: typer.Context,
    domain: str = typer.Argument(..., help=DOMAIN_HELP),
    match: str | None = typer.Option(None, "--match", help=MATCH_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Vendors associated with a company domain."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).companies.vendors(domain=domain, match=match), fmt=fmt)


@app.command()
@handle_errors
def subsidiaries(
    ctx: typer.Context,
    domain: str = typer.Argument(..., help=DOMAIN_HELP),
    match: str | None = typer.Option(None, "--match", help=MATCH_HELP),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Subsidiaries of a company domain."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).companies.subsidiaries(domain=domain, match=match), fmt=fmt)


@app.command(name="public-links")
@handle_errors
def public_links(
    ctx: typer.Context,
    domain: str = typer.Argument(..., help=DOMAIN_HELP),
    source: str = typer.Option(..., "--source", help="Public link source, e.g. crunchbase"),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Public profile links for a domain from a given source."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).companies.public_links(domain=domain, source=source), fmt=fmt)


@handle_errors
def extract_command(
    ctx: typer.Context,
    url: str = typer.Argument(..., help="Page URL to extract content from"),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Extract page content from a URL."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).companies.extract(url=url), fmt=fmt)
