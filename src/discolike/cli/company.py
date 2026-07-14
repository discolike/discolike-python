from __future__ import annotations

import typer

from discolike.cli._output import emit
from discolike.cli._output import handle_errors

app = typer.Typer(help="Look up company data by domain")


@app.command()
@handle_errors
def data(ctx: typer.Context, domain: str) -> None:
    from discolike.cli.main import get_client

    emit(get_client(ctx).companies.data(domain=domain))


@app.command()
@handle_errors
def score(ctx: typer.Context, domain: str) -> None:
    from discolike.cli.main import get_client

    emit(get_client(ctx).companies.score(domain=domain))


@app.command()
@handle_errors
def growth(ctx: typer.Context, domain: str) -> None:
    from discolike.cli.main import get_client

    emit(get_client(ctx).companies.growth(domain=domain))


@app.command()
@handle_errors
def metrics(ctx: typer.Context, domain: str) -> None:
    from discolike.cli.main import get_client

    emit(get_client(ctx).companies.metrics(domain=domain))


@app.command()
@handle_errors
def history(ctx: typer.Context, domain: str, max_records: int | None = typer.Option(None, "--max-records")) -> None:
    from discolike.cli.main import get_client

    emit(get_client(ctx).companies.history(domain=domain, max_records=max_records))


@app.command()
@handle_errors
def redirects(ctx: typer.Context, domain: str, match: str | None = typer.Option(None, "--match")) -> None:
    from discolike.cli.main import get_client

    emit(get_client(ctx).companies.redirects(domain=domain, match=match))


@app.command()
@handle_errors
def vendors(ctx: typer.Context, domain: str, match: str | None = typer.Option(None, "--match")) -> None:
    from discolike.cli.main import get_client

    emit(get_client(ctx).companies.vendors(domain=domain, match=match))


@app.command()
@handle_errors
def subsidiaries(ctx: typer.Context, domain: str, match: str | None = typer.Option(None, "--match")) -> None:
    from discolike.cli.main import get_client

    emit(get_client(ctx).companies.subsidiaries(domain=domain, match=match))


@app.command(name="public-links")
@handle_errors
def public_links(ctx: typer.Context, domain: str, source: str = typer.Option(..., "--source")) -> None:
    from discolike.cli.main import get_client

    emit(get_client(ctx).companies.public_links(domain=domain, source=source))


@handle_errors
def extract_command(ctx: typer.Context, url: str) -> None:
    from discolike.cli.main import get_client

    emit(get_client(ctx).companies.extract(url=url))
